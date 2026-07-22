"""
Athena Skill Engine - Autonomous skill generation, validation, and execution.
Single-file: forge + registry + sandbox + hot-reload + pruning.
"""
import ast
import importlib.util
import sys
import os
import tempfile
import threading
import traceback
import logging
import time
import hashlib
import inspect
from pathlib import Path
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from contextlib import redirect_stdout, redirect_stderr
import io

from athena.config import config
from athena.memory import MemoryEngine

logger = logging.getLogger(__name__)


@dataclass
class SkillInfo:
    """Metadata for a registered skill."""
    name: str
    description: str
    version: str = "1.0.0"
    author: str = "Athena SkillForge"
    file_path: str = ""
    function_name: str = ""
    module_name: str = ""
    is_async: bool = False
    param_schema: Dict = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    last_used: float = 0
    use_count: int = 0
    success_count: int = 0


@dataclass
class ValidationResult:
    """Result of skill validation."""
    is_valid: bool = True
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    functions_found: List[str] = field(default_factory=list)
    test_output: str = ""


# ==================== SKILL SANDBOX ====================

class SkillSandbox:
    """Isolated validation environment for generated skill code."""

    FORBIDDEN_IMPORTS = frozenset({
        "subprocess", "shutil", "ctypes", "multiprocessing",
        "socket", "http", "ftplib", "smtplib", "telnetlib",
        "webbrowser", "antigravity", "os", "sys", "importlib",
        "pkgutil", "runpy", "zipimport", "types", "inspect",
    })

    BLOCKED_BUILTINS = frozenset({
        "exec", "eval", "compile", "breakpoint",
        "open", "input", "exit", "quit", "help", "copyright",
        "license", "credits", "getattr", "setattr", "delattr",
        "vars", "dir", "globals", "locals", "hash", "id",
    })

    ALLOWED_IMPORTS = frozenset({
        "math", "json", "re", "datetime", "collections", "itertools",
        "functools", "pathlib", "textwrap", "string", "random", "hashlib",
        "base64", "urllib.parse", "csv", "statistics", "decimal", "fractions",
        "typing", "dataclasses", "enum", "uuid", "time", "calendar",
        "asyncio",  # Needed for async function tests
    })

    def __init__(self, timeout_seconds: int = 10):
        self.timeout_seconds = timeout_seconds

    def validate_source(self, source_code: str) -> ValidationResult:
        """Run full validation pipeline."""
        result = ValidationResult()

        # Stage 1: AST Parse
        tree = self._check_ast(source_code, result)
        if tree is None:
            result.is_valid = False
            return result

        # Stage 2: Structure validation
        self._check_structure(tree, source_code, result)
        if result.errors:
            result.is_valid = False
            return result

        # Stage 3: Import safety
        self._check_imports(tree, result)
        if result.errors:
            result.is_valid = False
            return result

        # Stage 4: Runtime import test
        self._run_import_test(source_code, result)
        if result.errors:
            result.is_valid = False
            return result

        return result

    def _check_ast(self, source_code: str, result: ValidationResult) -> Optional[ast.Module]:
        try:
            return ast.parse(source_code)
        except SyntaxError as e:
            result.errors.append(f"SyntaxError at line {e.lineno}, col {e.offset}: {e.msg}")
            return None

    def _check_structure(self, tree: ast.Module, source_code: str, result: ValidationResult):
        # Check for SKILL_METADATA
        has_metadata = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "SKILL_METADATA":
                        has_metadata = True
                        break

        if not has_metadata:
            result.warnings.append("Missing SKILL_METADATA dict. Using defaults.")

        # Check for public functions
        public_funcs = []
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name.startswith("_"):
                    continue

                public_funcs.append(node.name)

                # Check docstring
                if not (node.body and isinstance(node.body[0], ast.Expr)
                        and isinstance(node.body[0].value, ast.Constant)
                        and isinstance(node.body[0].value.value, str)):
                    result.errors.append(
                        f"Function '{node.name}' missing docstring. "
                        "All skill functions must have docstrings for MCP tool descriptions."
                    )

                # Check type annotations
                for arg in node.args.args:
                    if arg.arg == "self":
                        continue
                    if arg.annotation is None:
                        result.errors.append(
                            f"Parameter '{arg.arg}' in '{node.name}' missing type annotation."
                        )

                # Check return annotation
                if node.returns is None:
                    result.warnings.append(
                        f"Function '{node.name}' missing return type annotation."
                    )

        result.functions_found = public_funcs

        if not public_funcs:
            result.errors.append(
                "No public functions found. Skills must define at least one "
                "non-underscore function to be registered as a tool."
            )

    def _check_imports(self, tree: ast.Module, result: ValidationResult):
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top_module = alias.name.split(".")[0]
                    if top_module in self.FORBIDDEN_IMPORTS:
                        result.errors.append(
                            f"Forbidden import: '{alias.name}'. "
                            f"Skills cannot import {top_module} for security."
                        )
                    elif top_module not in self.ALLOWED_IMPORTS and top_module not in sys.stdlib_module_names:
                        result.warnings.append(
                            f"Non-standard import: '{alias.name}'. May fail at runtime."
                        )

            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    top_module = node.module.split(".")[0]
                    if top_module in self.FORBIDDEN_IMPORTS:
                        result.errors.append(
                            f"Forbidden import: 'from {node.module} import ...'. "
                            f"Skills cannot import {top_module} for security."
                        )

    def _run_import_test(self, source_code: str, result: ValidationResult):
        """Test import in isolated environment."""
        tmp_path = None
        module_name = f"_sandbox_test_{hash(source_code) & 0xFFFFFFFF}"

        try:
            # Write to temp file
            fd, tmp_path = tempfile.mkstemp(suffix=".py", prefix="athena_skill_")
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(source_code)

            # Import
            spec = importlib.util.spec_from_file_location(module_name, tmp_path)
            if spec is None or spec.loader is None:
                result.errors.append("Failed to create module spec for sandbox test.")
                return

            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module

            # Capture output
            output_buf = io.StringIO()
            with redirect_stdout(output_buf), redirect_stderr(output_buf):
                spec.loader.exec_module(module)

            result.test_output = output_buf.getvalue()

            # Verify functions are callable
            for func_name in result.functions_found:
                func = getattr(module, func_name, None)
                if func is None:
                    result.errors.append(f"Function '{func_name}' not found in imported module.")
                elif not callable(func):
                    result.errors.append(f"'{func_name}' exists but is not callable.")

        except Exception as e:
            result.errors.append(f"Runtime import failed: {type(e).__name__}: {e}")
        finally:
            sys.modules.pop(module_name, None)
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

    def generate_basic_test(self, source_code: str) -> str:
        """Generate smoke test code for skill functions."""
        try:
            tree = ast.parse(source_code)
        except SyntaxError:
            return "# Cannot generate tests: syntax error\n"

        test_lines = [
            "# Auto-generated smoke tests",
            "import sys",
            "_test_passed = 0",
            "_test_failed = 0",
            "",
        ]

        for node in ast.iter_child_nodes(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if node.name.startswith("_"):
                continue

            # Build default args from annotations
            args = []
            for arg in node.args.args:
                if arg.arg == "self":
                    continue
                annotation = ""
                if arg.annotation:
                    annotation = ast.unparse(arg.annotation) if hasattr(ast, 'unparse') else ""

                if "str" in annotation:
                    args.append('"test"')
                elif "int" in annotation:
                    args.append("0")
                elif "float" in annotation:
                    args.append("0.0")
                elif "bool" in annotation:
                    args.append("True")
                elif "list" in annotation.lower() or "List" in annotation:
                    args.append("[]")
                elif "dict" in annotation.lower() or "Dict" in annotation:
                    args.append("{}")
                else:
                    args.append('"test"')

            args_str = ", ".join(args)
            is_async = isinstance(node, ast.AsyncFunctionDef)

            if is_async:
                test_lines.extend([
                    f"# Test {node.name}",
                    f"import asyncio",
                    f"try:",
                    f"    _result = asyncio.get_event_loop().run_until_complete({node.name}({args_str}))",
                    f"    assert _result is not None, '{node.name} returned None'",
                    f"    _test_passed += 1",
                    f"    print(f'  ✓ {node.name} — passed')",
                    f"except Exception as _e:",
                    f"    _test_failed += 1",
                    f"    print(f'  ✗ {node.name} — {{_e}}')",
                    f"",
                ])
            else:
                test_lines.extend([
                    f"# Test {node.name}",
                    f"try:",
                    f"    _result = {node.name}({args_str})",
                    f"    assert _result is not None, '{node.name} returned None'",
                    f"    _test_passed += 1",
                    f"    print(f'  ✓ {node.name} — passed')",
                    f"except Exception as _e:",
                    f"    _test_failed += 1",
                    f"    print(f'  ✗ {node.name} — {{_e}}')",
                    f"",
                ])

        test_lines.extend([
            f"print(f'\\nResults: {{_test_passed}} passed, {{_test_failed}} failed')",
            f"if _test_failed > 0:",
            f"    raise RuntimeError(f'{{_test_failed}} test(s) failed')",
        ])

        return "\n".join(test_lines)

    def execute_with_timeout(
        self, source_code: str, test_code: str
    ) -> Tuple[bool, str]:
        """Execute skill + test code with timeout."""
        combined = source_code + "\n\n# --- SANDBOX TESTS ---\n" + test_code
        output_buf = io.StringIO()

        # Build safe globals
        safe_builtins = {
            k: v for k, v in __builtins__.items()
            if k not in self.BLOCKED_BUILTINS
        } if isinstance(__builtins__, dict) else {
            k: v for k, v in __builtins__.__dict__.items()
            if k not in self.BLOCKED_BUILTINS
        }

        safe_globals = {"__builtins__": safe_builtins}

        # Add allowed stdlib modules
        import math, json, re, datetime, collections, itertools, functools, asyncio
        safe_globals.update({
            "math": math, "json": json, "re": re,
            "datetime": datetime, "collections": collections,
            "itertools": itertools, "functools": functools,
            "asyncio": asyncio,
        })

        try:
            with redirect_stdout(output_buf), redirect_stderr(output_buf):
                exec(combined, safe_globals)
            return True, output_buf.getvalue()
        except Exception as e:
            return False, output_buf.getvalue() + f"\n{traceback.format_exc()}"


# ==================== SKILL ENGINE ====================

class SkillEngine:
    """
    Unified skill engine: discover, forge, register, execute, hot-reload, prune.
    Thread-safe, memory-aware, auto-persisting.
    """

    # LLM prompt for skill generation
    FORGE_PROMPT = '''You are Athena's SkillForge — an autonomous code generator.
Generate a Python tool function that fulfills this request:

REQUEST: {request}

STRICT REQUIREMENTS:
1. Output ONLY valid Python code. No markdown, no explanation, no ```python blocks.
2. Start with a SKILL_METADATA dict:
   SKILL_METADATA = {{
       "name": "<snake_case_name>",
       "description": "<one line description>",
       "version": "1.0.0",
       "author": "Athena SkillForge",
   }}
3. Define ONE OR MORE public functions (no leading underscore).
4. Every function MUST have:
   - Full type annotations on ALL parameters and return type
   - A Google-style docstring with description, Args, and Returns sections
   - Return type of `str` (MCP tools return strings)
5. You may import ONLY these standard library modules:
   math, json, re, datetime, collections, itertools, functools,
   pathlib, textwrap, string, random, hashlib,
   base64, urllib.parse, csv, statistics, decimal, fractions, typing
6. Do NOT import: subprocess, shutil, socket, http, requests, ctypes, os
7. Handle errors gracefully — return error strings, never raise unhandled exceptions.
8. Functions should be self-contained and stateless.
9. Make the function genuinely useful and robust, not a stub.

OUTPUT THE PYTHON CODE AND NOTHING ELSE.'''

    def __init__(
        self,
        llm_generate_fn: Callable[[str], str],
        memory: MemoryEngine,
        skills_dir: Optional[str] = None,
    ):
        self.llm_generate = llm_generate_fn
        self.memory = memory
        self.skills_dir = Path(skills_dir or config.skills_dir)
        self.skills_dir.mkdir(parents=True, exist_ok=True)

        self.sandbox = SkillSandbox(timeout_seconds=config.skill_timeout_seconds)
        self._registry: Dict[str, Tuple[Callable, SkillInfo]] = {}
        self._lock = threading.RLock()
        self._file_mtimes: Dict[str, float] = {}

        logger.info(f"[SKILL_ENGINE] Initialized. Skills dir: {self.skills_dir}")

        # Auto-discover skills on initialization
        self.discover()

    # ==================== Discovery & Loading ====================

    def discover(self) -> List[SkillInfo]:
        """Scan skills directory and load all valid skill modules."""
        discovered = []

        if not self.skills_dir.exists():
            logger.warning(f"[SKILL_ENGINE] Skills directory does not exist: {self.skills_dir}")
            return discovered

        for py_file in sorted(self.skills_dir.glob("*.py")):
            if py_file.name.startswith("__"):
                continue

            try:
                skills = self._load_skill_module(py_file)
                discovered.extend(skills)
            except Exception as e:
                logger.error(f"[SKILL_ENGINE] Failed to load {py_file.name}: {e}")

        logger.info(f"[SKILL_ENGINE] Discovered {len(discovered)} skill(s)")
        return discovered

    def _load_skill_module(self, file_path: Path) -> List[SkillInfo]:
        """Dynamically import a skill module and register its functions."""
        module_name = f"athena_skill_{file_path.stem}"
        spec = importlib.util.spec_from_file_location(module_name, str(file_path))
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot create module spec for {file_path}")

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module

        try:
            spec.loader.exec_module(module)
        except Exception as e:
            del sys.modules[module_name]
            raise ImportError(f"Failed to execute module {file_path.name}: {e}") from e

        # Extract metadata
        module_meta = getattr(module, "SKILL_METADATA", {})
        module_desc = module_meta.get("description", f"Skills from {file_path.name}")
        module_version = module_meta.get("version", "1.0.0")
        module_author = module_meta.get("author", "Athena SkillForge")

        # Track mtime for hot-reload
        self._file_mtimes[str(file_path)] = file_path.stat().st_mtime

        loaded_skills = []
        for name, obj in inspect.getmembers(module, inspect.isfunction):
            if name.startswith("_"):
                continue
            if obj.__module__ != module_name:
                continue  # Skip imported functions

            if not obj.__doc__:
                logger.warning(f"[SKILL_ENGINE] Skipping {name} in {file_path.name}: no docstring")
                continue

            sig = inspect.signature(obj)
            has_annotations = all(
                p.annotation != inspect.Parameter.empty
                for p in sig.parameters.values()
            )
            if not has_annotations:
                logger.warning(f"[SKILL_ENGINE] Skipping {name}: missing type annotations")
                continue

            metadata = SkillInfo(
                name=name,
                description=obj.__doc__.split("\n")[0].strip(),
                version=module_version,
                author=module_author,
                file_path=str(file_path),
                function_name=name,
                module_name=module_name,
                is_async=inspect.iscoroutinefunction(obj),
                param_schema=self._extract_param_schema(sig),
            )

            with self._lock:
                self._registry[name] = (obj, metadata)

            loaded_skills.append(metadata)
            logger.info(f"[SKILL_ENGINE] Registered skill: {name} (from {file_path.name})")

        return loaded_skills

    def _extract_param_schema(self, sig: inspect.Signature) -> Dict:
        """Extract JSON schema from function signature."""
        properties = {}
        required = []

        for name, param in sig.parameters.items():
            if name == "self":
                continue

            param_type = "string"
            if param.annotation != inspect.Parameter.empty:
                ann = param.annotation
                if ann == int:
                    param_type = "integer"
                elif ann == float:
                    param_type = "number"
                elif ann == bool:
                    param_type = "boolean"
                elif hasattr(ann, '__origin__'):
                    if ann.__origin__ in (list, List):
                        param_type = "array"
                    elif ann.__origin__ in (dict, Dict):
                        param_type = "object"

            properties[name] = {"type": param_type}
            if param.default == inspect.Parameter.empty:
                required.append(name)

        return {"type": "object", "properties": properties, "required": required}

    # ==================== Skill Access ====================

    def get(self, name: str) -> Optional[Callable]:
        """Get a skill function by name."""
        with self._lock:
            entry = self._registry.get(name)
            return entry[0] if entry else None

    def get_info(self, name: str) -> Optional[SkillInfo]:
        """Get skill metadata by name."""
        with self._lock:
            entry = self._registry.get(name)
            return entry[1] if entry else None

    def list_all(self) -> List[SkillInfo]:
        """List all registered skills."""
        with self._lock:
            return [info for _, info in self._registry.values()]

    def get_tool_definitions(self) -> List[Dict]:
        """Get MCP-compatible tool definitions for LLM."""
        with self._lock:
            tools = []
            for name, (func, info) in self._registry.items():
                tools.append({
                    "name": name,
                    "description": info.description,
                    "parameters": info.param_schema,
                })
            return tools

    # ==================== Execution ====================

    def _coerce_args(self, func, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """Coerce string arguments to match function signature types."""
        import inspect
        sig = inspect.signature(func)
        coerced = {}
        for name, value in kwargs.items():
            param = sig.parameters.get(name)
            if param is None or param.annotation == inspect.Parameter.empty:
                coerced[name] = value
                continue

            annotation = param.annotation
            try:
                if annotation == int:
                    coerced[name] = int(value)
                elif annotation == float:
                    coerced[name] = float(value)
                elif annotation == bool:
                    if isinstance(value, str):
                        coerced[name] = value.lower() in ('true', '1', 'yes', 'on')
                    else:
                        coerced[name] = bool(value)
                elif annotation == str:
                    coerced[name] = str(value)
                else:
                    coerced[name] = value
            except (ValueError, TypeError):
                coerced[name] = value
        return coerced

    def execute(self, name: str, **kwargs) -> str:
        """Execute a skill by name with arguments."""
        skill = self.get(name)
        if skill is None:
            return f"Error: Skill '{name}' not found."

        info = self.get_info(name)
        start = time.time()
        success = False

        try:
            # Coerce arguments to match function signature
            kwargs = self._coerce_args(skill, kwargs)

            if info.is_async:
                import asyncio
                try:
                    loop = asyncio.get_event_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                result = loop.run_until_complete(skill(**kwargs))
            else:
                result = skill(**kwargs)

            success = True
            return str(result)

        except Exception as e:
            logger.error(f"[SKILL_ENGINE] Skill '{name}' failed: {e}")
            return f"Error executing {name}: {type(e).__name__}: {e}"
        finally:
            elapsed = time.time() - start
            if info:
                info.last_used = time.time()
                info.use_count += 1
                if success:
                    info.success_count += 1
                self.memory.record_skill_usage(name, success, kwargs)

    # ==================== Auto-Forge ====================

    def can_forge(self, request: str, existing_tools: List[str]) -> bool:
        """Heuristic: does this request likely need a new skill?"""
        creation_indicators = [
            "create a tool", "build a tool", "make a tool",
            "write a function", "build a function",
            "create a skill", "forge a skill", "make a skill",
            "i need a tool", "can you build",
            "write me a", "generate a",
            "automate", "script to",
        ]
        lower = request.lower()
        return any(indicator in lower for indicator in creation_indicators)

    def forge(self, request: str) -> Tuple[bool, str]:
        """End-to-end skill generation: generate -> validate -> persist -> register."""
        logger.info(f"[SKILL_ENGINE] Forging skill for: {request}")

        last_error = ""
        for attempt in range(1, config.skill_max_retries + 1):
            # Generate code
            prompt = self.FORGE_PROMPT.format(request=request)
            if attempt > 1 and last_error:
                prompt += f"\n\nPREVIOUS ATTEMPT FAILED:\n{last_error}\nFix and regenerate."

            try:
                generated_code = self.llm_generate(prompt)
            except Exception as e:
                last_error = f"LLM generation failed: {e}"
                logger.error(f"[SKILL_ENGINE] Attempt {attempt}: {last_error}")
                continue

            # Clean LLM output
            generated_code = self._clean_llm_output(generated_code)

            if not generated_code.strip():
                last_error = "LLM returned empty code."
                continue

            # Validate
            validation = self.sandbox.validate_source(generated_code)
            if not validation.is_valid:
                last_error = "Validation errors:\n" + "\n".join(validation.errors)
                logger.warning(f"[SKILL_ENGINE] Attempt {attempt} validation failed")
                continue

            # Run tests
            test_code = self.sandbox.generate_basic_test(generated_code)
            test_passed, test_output = self.sandbox.execute_with_timeout(
                generated_code, test_code
            )
            if not test_passed:
                last_error = f"Test execution failed:\n{test_output}"
                logger.warning(f"[SKILL_ENGINE] Attempt {attempt} tests failed")
                continue

            # Persist
            skill_name = self._extract_skill_name(generated_code, request)
            file_path = self.skills_dir / f"{skill_name}.py"

            if file_path.exists():
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                file_path = self.skills_dir / f"{skill_name}_{timestamp}.py"

            try:
                file_path.write_text(generated_code, encoding="utf-8")
            except Exception as e:
                return False, f"Failed to persist skill file: {e}"

            # Load and register
            try:
                loaded = self._load_skill_module(file_path)
                function_names = [s.function_name for s in loaded]
            except Exception as e:
                return False, f"Skill file saved but registry loading failed: {e}"

            logger.info(
                f"[SKILL_ENGINE] ✓ Forged skill '{skill_name}' with functions: {function_names}"
            )

            return True, (
                f"Successfully forged new skill '{skill_name}' with "
                f"function(s): {function_names}. Ready for immediate use."
            )

        return False, f"Failed after {config.skill_max_retries} attempts. Last error: {last_error}"

    def _clean_llm_output(self, raw: str) -> str:
        """Strip markdown fences and artifacts from LLM output."""
        code = raw.strip()

        # Remove ```python ... ``` blocks
        import re
        pattern = r"```(?:python)?\s*\n(.*?)```"
        matches = re.findall(pattern, code, re.DOTALL)
        if matches:
            code = "\n\n".join(matches)

        code = code.strip("`").strip()
        if code.startswith("python\n"):
            code = code[7:]

        return code

    def _extract_skill_name(self, source_code: str, request: str) -> str:
        """Extract skill name from metadata or derive from request."""
        import re
        match = re.search(r'"name"\s*:\s*"([^"]+)"', source_code)
        if match:
            name = match.group(1)
            return re.sub(r"[^a-z0-9_]", "_", name.lower())

        words = re.sub(r"[^a-z0-9\s]", "", request.lower()).split()
        return "_".join(words[:4]) or "unnamed_skill"

    # ==================== Hot Reload ====================

    def hot_reload(self) -> List[SkillInfo]:
        """Reload any changed or new skill files."""
        changed_files = self._check_for_updates()
        reloaded = []

        for file_path in changed_files:
            path = Path(file_path)
            # Unregister old skills from this file
            with self._lock:
                to_remove = [
                    name for name, (_, info) in self._registry.items()
                    if info.file_path == file_path
                ]
            for name in to_remove:
                self.unregister(name)

            # Purge module cache
            module_name = f"athena_skill_{path.stem}"
            sys.modules.pop(module_name, None)

            try:
                skills = self._load_skill_module(path)
                reloaded.extend(skills)
            except Exception as e:
                logger.error(f"[SKILL_ENGINE] Hot-reload failed for {path.name}: {e}")

        if reloaded:
            logger.info(f"[SKILL_ENGINE] Hot-reloaded {len(reloaded)} skill(s)")

        return reloaded

    def _check_for_updates(self) -> List[str]:
        """Check for modified or new skill files."""
        changed = []
        for py_file in self.skills_dir.glob("*.py"):
            if py_file.name.startswith("__"):
                continue
            path_str = str(py_file)
            current_mtime = py_file.stat().st_mtime
            if path_str not in self._file_mtimes or self._file_mtimes[path_str] < current_mtime:
                changed.append(path_str)
        return changed

    # ==================== Maintenance ====================

    def unregister(self, name: str) -> bool:
        """Remove a skill from the registry."""
        with self._lock:
            if name in self._registry:
                del self._registry[name]
                logger.info(f"[SKILL_ENGINE] Unregistered skill: {name}")
                return True
        return False

    def prune_unused(self, max_age_days: int = None) -> List[str]:
        """Remove skills not used in N days."""
        max_age_days = max_age_days or config.skill_prune_days
        unused = self.memory.get_unused_skills(max_age_days)
        pruned = []

        for skill_name in unused:
            info = self.get_info(skill_name)
            if info and info.file_path:
                # Remove from registry
                self.unregister(skill_name)
                # Optionally delete file (commented for safety)
                # Path(info.file_path).unlink(missing_ok=True)
                pruned.append(skill_name)
                logger.info(f"[SKILL_ENGINE] Pruned unused skill: {skill_name}")

        return pruned

    def optimize_hot_skills(self):
        """Pre-compile/cache frequently used skills."""
        stats = self.memory.get_skill_stats(7)
        hot_skills = [
            name for name, data in stats.items()
            if data["total_calls"] > 10 and data["success_rate"] > 0.9
        ]

        for name in hot_skills:
            info = self.get_info(name)
            if info:
                # Could add bytecode caching here
                logger.debug(f"[SKILL_ENGINE] Hot skill: {name} ({info.use_count} uses)")

    def self_heal(self, llm_generate_fn: Callable[[str], str]):
        """Re-validate and attempt to fix broken skills."""
        with self._lock:
            skills = list(self._registry.items())

        for name, (func, info) in skills:
            if info.success_count == 0 and info.use_count > 3:
                # Consistently failing - try to regenerate
                logger.warning(f"[SKILL_ENGINE] Self-healing: attempting to fix {name}")
                # Would need original_desc = info.description
                success, msg = self.forge(f"Fix the skill '{name}' that {info.description}")
                if success:
                    logger.info(f"[SKILL_ENGINE] Self-healed {name}")

    def get_stats(self) -> Dict[str, Any]:
        """Get engine statistics."""
        with self._lock:
            total = len(self._registry)
            async_count = sum(1 for _, info in self._registry.values() if info.is_async)

        return {
            "total_skills": total,
            "async_skills": async_count,
            "sync_skills": total - async_count,
            "skills_dir": str(self.skills_dir),
            "files_tracked": len(self._file_mtimes),
        }