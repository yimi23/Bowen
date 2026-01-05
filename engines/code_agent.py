#!/usr/bin/env python3
"""
BOWEN Code Generation & Deployment Engine
Writes production code, builds projects, deploys to hosting
"""

import os
import json
import logging
import subprocess
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

class CodeAgent:
    """
    Autonomous code generation and deployment system that:
    1. Generates production-ready code (React, Python, etc.)
    2. Creates complete project structures
    3. Writes tests
    4. Deploys to Vercel/Netlify/hosting
    5. Manages git workflows
    6. Builds full-stack applications
    """
    
    def __init__(self, workspace: str = "/Users/yimi/Desktop", claude_engine=None):
        """Initialize with workspace directory and Claude engine"""
        self.workspace = Path(workspace)
        self.claude_engine = claude_engine
        self.projects_dir = self.workspace / "bowen_projects"
        
        # Ensure projects directory exists
        self.projects_dir.mkdir(exist_ok=True)
        
        # Project templates
        self.templates = {
            "react_app": self._get_react_template(),
            "next_app": self._get_next_template(),
            "python_api": self._get_python_api_template(),
            "electron_app": self._get_electron_template(),
            "fullstack": self._get_fullstack_template()
        }
        
        logger.info(f"Code Agent initialized with workspace: {self.workspace}")
    
    def create_project(self, project_type: str, name: str, spec: Dict[str, Any]) -> str:
        """
        Create complete project structure based on type and specification
        """
        try:
            project_path = self.projects_dir / name
            
            if project_path.exists():
                # Add timestamp to avoid conflicts
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                project_path = self.projects_dir / f"{name}_{timestamp}"
            
            project_path.mkdir(exist_ok=True)
            
            logger.info(f"Creating {project_type} project: {name}")
            
            if project_type == "react_app":
                return self._create_react_app(project_path, spec)
            elif project_type == "next_app":
                return self._create_next_app(project_path, spec)
            elif project_type == "python_api":
                return self._create_python_api(project_path, spec)
            elif project_type == "electron_app":
                return self._create_electron_app(project_path, spec)
            elif project_type == "fullstack":
                return self._create_fullstack_app(project_path, spec)
            else:
                return self._create_generic_project(project_path, spec)
                
        except Exception as e:
            logger.error(f"Error creating project: {e}")
            return f"Error creating project: {str(e)}"
    
    def _create_react_app(self, project_path: Path, spec: Dict[str, Any]) -> str:
        """Create a React application with specified features"""
        try:
            # Use Create React App or Vite based on preference
            use_vite = spec.get('use_vite', True)
            
            if use_vite:
                # Create Vite React app
                result = subprocess.run([
                    'npm', 'create', 'vite@latest', str(project_path.name), '--template', 'react-ts'
                ], cwd=str(project_path.parent), capture_output=True, text=True)
                
                if result.returncode != 0:
                    raise Exception(f"Vite creation failed: {result.stderr}")
            else:
                # Create React App
                result = subprocess.run([
                    'npx', 'create-react-app', str(project_path.name), '--template', 'typescript'
                ], cwd=str(project_path.parent), capture_output=True, text=True)
                
                if result.returncode != 0:
                    raise Exception(f"CRA creation failed: {result.stderr}")
            
            # Add additional dependencies
            self._add_dependencies(project_path, spec.get('dependencies', []))
            
            # Generate components based on spec
            if 'components' in spec:
                for component_spec in spec['components']:
                    self.write_component(component_spec, project_path)
            
            # Add styling
            if spec.get('styling') == 'tailwind':
                self._add_tailwind(project_path)
            
            # Create README with project info
            self._create_readme(project_path, 'React App', spec)
            
            return str(project_path)
            
        except Exception as e:
            logger.error(f"Error creating React app: {e}")
            return f"Error: {str(e)}"
    
    def _create_next_app(self, project_path: Path, spec: Dict[str, Any]) -> str:
        """Create a Next.js application"""
        try:
            result = subprocess.run([
                'npx', 'create-next-app@latest', str(project_path.name),
                '--typescript', '--tailwind', '--eslint', '--app'
            ], cwd=str(project_path.parent), capture_output=True, text=True)
            
            if result.returncode != 0:
                raise Exception(f"Next.js creation failed: {result.stderr}")
            
            # Add auth if specified
            if 'auth' in spec.get('features', []):
                self._add_nextauth(project_path)
            
            # Add database if specified
            if 'database' in spec.get('features', []):
                self._add_database_setup(project_path, spec.get('database', 'postgres'))
            
            return str(project_path)
            
        except Exception as e:
            logger.error(f"Error creating Next.js app: {e}")
            return f"Error: {str(e)}"
    
    def _create_python_api(self, project_path: Path, spec: Dict[str, Any]) -> str:
        """Create a Python FastAPI application"""
        try:
            # Create basic FastAPI structure
            (project_path / "app").mkdir()
            (project_path / "tests").mkdir()
            (project_path / "docs").mkdir()
            
            # Create main.py
            main_py = '''from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="API", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Hello World"}

@app.get("/health")
def health_check():
    return {"status": "healthy"}
'''
            (project_path / "app" / "main.py").write_text(main_py)
            
            # Create requirements.txt
            requirements = ['fastapi', 'uvicorn[standard]', 'python-multipart', 'python-dotenv']
            
            if 'database' in spec.get('features', []):
                db_type = spec.get('database', 'postgres')
                if db_type == 'postgres':
                    requirements.extend(['psycopg2-binary', 'sqlalchemy'])
                elif db_type == 'mysql':
                    requirements.extend(['pymysql', 'sqlalchemy'])
                elif db_type == 'sqlite':
                    requirements.append('sqlalchemy')
            
            if 'auth' in spec.get('features', []):
                requirements.extend(['python-jose[cryptography]', 'passlib[bcrypt]'])
            
            (project_path / "requirements.txt").write_text('\n'.join(requirements))
            
            # Create Dockerfile
            dockerfile = '''FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
'''
            (project_path / "Dockerfile").write_text(dockerfile)
            
            # Create .env.example
            env_example = '''DATABASE_URL=postgresql://user:password@localhost/dbname
SECRET_KEY=your-secret-key-here
API_ENV=development
'''
            (project_path / ".env.example").write_text(env_example)
            
            return str(project_path)
            
        except Exception as e:
            logger.error(f"Error creating Python API: {e}")
            return f"Error: {str(e)}"
    
    def write_component(self, component_spec: Dict[str, Any], project_path: Path = None) -> str:
        """
        Generate React/Vue component with VALIDATION - ANTI-HALLUCINATION
        """
        try:
            if not self.claude_engine:
                raise Exception("Claude engine not available for component generation")
            
            component_name = component_spec.get('name', 'Component')
            component_type = component_spec.get('type', 'functional')
            props = component_spec.get('props', [])
            styling = component_spec.get('styling', 'css')
            
            # Generate component code using Claude with ANTI-HALLUCINATION rules
            prompt = f"""
            CRITICAL CODE GENERATION RULES (ANTI-HALLUCINATION):
            1. ONLY use real React/TypeScript syntax and APIs
            2. Do NOT invent React hooks or methods that don't exist
            3. Use ONLY standard TypeScript interfaces
            4. Include ONLY imports that actually exist
            5. Generate COMPILABLE code (will be tested)
            
            Generate a React TypeScript component with these specifications:
            
            Component Name: {component_name}
            Type: {component_type} component
            Props: {json.dumps(props, indent=2)}
            Styling: {styling}
            
            REAL REQUIREMENTS (no made-up features):
            1. Standard TypeScript interfaces for props
            2. Basic error handling with try/catch
            3. Standard ARIA attributes for accessibility
            4. CSS modules or Tailwind classes (no invented styling)
            5. Clean, COMPILABLE production code
            
            Additional features: {json.dumps(component_spec.get('features', []))}
            
            VALIDATION REQUIREMENTS:
            - Code MUST compile with TypeScript
            - Imports MUST be real packages
            - React hooks MUST be standard ones (useState, useEffect, etc.)
            - No invented APIs or methods
            
            Return ONLY the component code - NO explanations or markdown.
            """
            
            response = self.claude_engine.client.messages.create(
                model=self.claude_engine.model,
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}]
            )
            
            component_code = response.content[0].text
            
            # Clean up code formatting
            if component_code.startswith('```'):
                component_code = component_code.split('\n', 1)[1]
                component_code = component_code.rsplit('\n', 1)[0]
                if component_code.endswith('```'):
                    component_code = component_code[:-3]
            
            # CRITICAL: Validate generated code (anti-hallucination)
            validation_result = self._validate_typescript_code(component_code, component_name)
            
            if not validation_result['valid']:
                logger.warning(f"Generated code failed validation: {validation_result['error']}")
                # Return error instead of invalid code
                return f"Code generation failed validation: {validation_result['error']}"
            
            # Save component if project path provided
            if project_path:
                components_dir = project_path / "src" / "components"
                components_dir.mkdir(parents=True, exist_ok=True)
                
                component_file = components_dir / f"{component_name}.tsx"
                component_file.write_text(component_code)
                
                # Generate test file
                test_code = self._generate_component_test(component_name, props)
                test_file = project_path / "src" / "__tests__" / f"{component_name}.test.tsx"
                test_file.parent.mkdir(parents=True, exist_ok=True)
                test_file.write_text(test_code)
            
            return component_code
            
        except Exception as e:
            logger.error(f"Error writing component: {e}")
            return f"Error: {str(e)}"
    
    def write_api_endpoint(self, endpoint_spec: Dict[str, Any]) -> str:
        """
        Generate API endpoint with validation, error handling, database queries
        """
        try:
            if not self.claude_engine:
                raise Exception("Claude engine not available for API generation")
            
            endpoint_name = endpoint_spec.get('name', 'endpoint')
            method = endpoint_spec.get('method', 'GET')
            path = endpoint_spec.get('path', f'/{endpoint_name}')
            
            prompt = f"""
            Generate a FastAPI endpoint with these specifications:
            
            Endpoint: {method} {path}
            Name: {endpoint_name}
            
            Requirements:
            1. Input validation using Pydantic models
            2. Proper error handling with HTTP status codes
            3. Database integration (if needed)
            4. Response formatting
            5. Type hints
            6. Docstring
            
            Features: {json.dumps(endpoint_spec.get('features', []))}
            Database: {endpoint_spec.get('database', 'none')}
            Authentication: {endpoint_spec.get('auth', False)}
            
            Return only the Python code without explanations.
            """
            
            response = self.claude_engine.client.messages.create(
                model=self.claude_engine.model,
                max_tokens=1500,
                messages=[{"role": "user", "content": prompt}]
            )
            
            return response.content[0].text
            
        except Exception as e:
            logger.error(f"Error writing API endpoint: {e}")
            return f"Error: {str(e)}"
    
    def deploy_to_vercel(self, project_path: str) -> Dict[str, Any]:
        """
        Deploy project to Vercel
        1. Initialize git if needed
        2. Commit code
        3. Push to GitHub (optional)
        4. Deploy to Vercel via CLI
        5. Return deployment URL
        """
        try:
            project_path = Path(project_path)
            
            # Check if Vercel CLI is installed
            vercel_check = subprocess.run(['vercel', '--version'], capture_output=True)
            if vercel_check.returncode != 0:
                return {
                    "success": False,
                    "error": "Vercel CLI not installed. Install with: npm i -g vercel"
                }
            
            # Initialize git if needed
            if not (project_path / ".git").exists():
                subprocess.run(['git', 'init'], cwd=project_path, capture_output=True)
                subprocess.run(['git', 'add', '.'], cwd=project_path, capture_output=True)
                subprocess.run([
                    'git', 'commit', '-m', 'Initial commit - BOWEN generated project'
                ], cwd=project_path, capture_output=True)
            
            # Deploy to Vercel
            deploy_result = subprocess.run([
                'vercel', '--prod', '--yes'
            ], cwd=project_path, capture_output=True, text=True)
            
            if deploy_result.returncode == 0:
                # Extract URL from output
                output_lines = deploy_result.stdout.split('\n')
                url = None
                for line in output_lines:
                    if 'https://' in line and '.vercel.app' in line:
                        url = line.strip()
                        break
                
                return {
                    "success": True,
                    "url": url,
                    "deployment_id": "generated",
                    "platform": "vercel"
                }
            else:
                return {
                    "success": False,
                    "error": deploy_result.stderr,
                    "output": deploy_result.stdout
                }
                
        except Exception as e:
            logger.error(f"Error deploying to Vercel: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def run_tests(self, project_path: str) -> Dict[str, Any]:
        """Run project tests and return results"""
        try:
            project_path = Path(project_path)
            
            # Detect test framework
            package_json_path = project_path / "package.json"
            if package_json_path.exists():
                # JavaScript/TypeScript project
                result = subprocess.run([
                    'npm', 'test', '--', '--watchAll=false', '--passWithNoTests'
                ], cwd=project_path, capture_output=True, text=True)
                
                return {
                    "success": result.returncode == 0,
                    "output": result.stdout,
                    "errors": result.stderr,
                    "framework": "jest"
                }
            
            # Python project
            elif (project_path / "requirements.txt").exists():
                # Try pytest first
                pytest_result = subprocess.run([
                    'pytest', '-v'
                ], cwd=project_path, capture_output=True, text=True)
                
                if pytest_result.returncode != 127:  # pytest found
                    return {
                        "success": pytest_result.returncode == 0,
                        "output": pytest_result.stdout,
                        "errors": pytest_result.stderr,
                        "framework": "pytest"
                    }
                
                # Fallback to unittest
                unittest_result = subprocess.run([
                    'python', '-m', 'unittest', 'discover', '-v'
                ], cwd=project_path, capture_output=True, text=True)
                
                return {
                    "success": unittest_result.returncode == 0,
                    "output": unittest_result.stdout,
                    "errors": unittest_result.stderr,
                    "framework": "unittest"
                }
            
            else:
                return {
                    "success": False,
                    "error": "No test framework detected"
                }
                
        except Exception as e:
            logger.error(f"Error running tests: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _add_dependencies(self, project_path: Path, dependencies: List[str]):
        """Add npm dependencies to project"""
        if dependencies:
            subprocess.run([
                'npm', 'install', '--save', *dependencies
            ], cwd=project_path, capture_output=True)
    
    def _add_tailwind(self, project_path: Path):
        """Add Tailwind CSS to React project"""
        # Install Tailwind
        subprocess.run([
            'npm', 'install', '-D', 'tailwindcss', 'postcss', 'autoprefixer'
        ], cwd=project_path, capture_output=True)
        
        # Initialize Tailwind config
        subprocess.run([
            'npx', 'tailwindcss', 'init', '-p'
        ], cwd=project_path, capture_output=True)
        
        # Update tailwind.config.js
        tailwind_config = '''/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/**/*.{js,jsx,ts,tsx}",
  ],
  theme: {
    extend: {},
  },
  plugins: [],
}'''
        (project_path / "tailwind.config.js").write_text(tailwind_config)
        
        # Add Tailwind directives to CSS
        css_content = '''@tailwind base;
@tailwind components;
@tailwind utilities;'''
        
        css_file = project_path / "src" / "index.css"
        if css_file.exists():
            css_file.write_text(css_content)
    
    def _generate_component_test(self, component_name: str, props: List[Dict]) -> str:
        """Generate basic test file for React component"""
        return f'''import {{ render, screen }} from '@testing-library/react';
import {component_name} from '../components/{component_name}';

test('renders {component_name} component', () => {{
  render(<{component_name} />);
  // Add specific test assertions here
}});
'''
    
    def _create_readme(self, project_path: Path, project_type: str, spec: Dict[str, Any]):
        """Create README.md for project"""
        readme_content = f"""# {project_path.name}

{project_type} project generated by BOWEN Framework

## Features

{chr(10).join(f'- {feature}' for feature in spec.get('features', []))}

## Getting Started

### Prerequisites

- Node.js 18+ (for frontend projects)
- Python 3.11+ (for backend projects)

### Installation

```bash
# Install dependencies
npm install  # for Node.js projects
pip install -r requirements.txt  # for Python projects
```

### Development

```bash
# Start development server
npm start  # for React/Next.js
uvicorn app.main:app --reload  # for FastAPI
```

### Build

```bash
# Build for production
npm run build
```

### Deploy

```bash
# Deploy to Vercel
vercel --prod
```

## Project Structure

```
{project_path.name}/
├── src/          # Source code
├── tests/        # Test files
├── docs/         # Documentation
└── README.md     # This file
```

## Generated by BOWEN

This project was automatically generated by the BOWEN Framework.
Generation date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        (project_path / "README.md").write_text(readme_content)
    
    def _get_react_template(self) -> Dict[str, str]:
        """Get React app template files"""
        return {
            "package.json": {
                "name": "bowen-react-app",
                "version": "0.1.0",
                "dependencies": {
                    "react": "^18.2.0",
                    "react-dom": "^18.2.0",
                    "typescript": "^4.9.5"
                }
            }
        }
    
    def _get_next_template(self) -> Dict[str, str]:
        """Get Next.js template files"""
        return {}
    
    def _get_python_api_template(self) -> Dict[str, str]:
        """Get Python API template files"""
        return {}
    
    def _get_electron_template(self) -> Dict[str, str]:
        """Get Electron template files"""
        return {}
    
    def _get_fullstack_template(self) -> Dict[str, str]:
        """Get full-stack template files"""
        return {}
    
    def _create_electron_app(self, project_path: Path, spec: Dict[str, Any]) -> str:
        """Create Electron application"""
        # Implementation for Electron app creation
        return str(project_path)
    
    def _create_fullstack_app(self, project_path: Path, spec: Dict[str, Any]) -> str:
        """Create full-stack application"""
        # Implementation for full-stack app creation
        return str(project_path)
    
    def _create_generic_project(self, project_path: Path, spec: Dict[str, Any]) -> str:
        """Create generic project structure"""
        # Create basic directories
        (project_path / "src").mkdir()
        (project_path / "tests").mkdir()
        (project_path / "docs").mkdir()
        
        # Create basic README
        self._create_readme(project_path, "Generic Project", spec)
        
        return str(project_path)
    
    def _add_nextauth(self, project_path: Path):
        """Add NextAuth.js to Next.js project"""
        subprocess.run([
            'npm', 'install', 'next-auth'
        ], cwd=project_path, capture_output=True)
    
    def _add_database_setup(self, project_path: Path, db_type: str):
        """Add database setup to project"""
        if db_type == 'postgres':
            subprocess.run([
                'npm', 'install', 'pg', '@types/pg'
            ], cwd=project_path, capture_output=True)
        elif db_type == 'mysql':
            subprocess.run([
                'npm', 'install', 'mysql2'
            ], cwd=project_path, capture_output=True)
    
    def _validate_typescript_code(self, code: str, component_name: str) -> Dict[str, Any]:
        """
        Validate TypeScript code to prevent hallucinated APIs - ANTI-HALLUCINATION
        """
        try:
            # Basic syntax validation
            if not code.strip():
                return {"valid": False, "error": "Empty code generated"}
            
            # Check for basic React component structure
            if f"const {component_name}" not in code and f"function {component_name}" not in code:
                return {"valid": False, "error": f"Component {component_name} not found in code"}
            
            # Check for valid React imports (no hallucinated ones)
            valid_react_imports = [
                "React", "useState", "useEffect", "useContext", "useCallback", 
                "useMemo", "useRef", "useReducer", "Component", "Fragment"
            ]
            
            import_lines = [line for line in code.split('\n') if line.strip().startswith('import')]
            
            for import_line in import_lines:
                # Check for suspicious imports that might be hallucinated
                if 'react' in import_line.lower():
                    # Extract imported items
                    if 'from "react"' in import_line or "from 'react'" in import_line:
                        # Valid React import
                        continue
                    else:
                        # Check if trying to import from non-existent React packages
                        suspicious_packages = [
                            'react-super', 'react-advanced', 'react-magic', 
                            'react-auto', 'react-enhanced'
                        ]
                        if any(pkg in import_line.lower() for pkg in suspicious_packages):
                            return {"valid": False, "error": f"Suspicious React package in import: {import_line}"}
            
            # Check for obviously invalid TypeScript syntax
            syntax_checks = [
                ('interface' in code and '{' in code and '}' in code) or 'interface' not in code,  # Valid interface syntax
                'export default' in code or 'export {' in code,  # Valid export
                code.count('{') == code.count('}') or abs(code.count('{') - code.count('}')) <= 1  # Balanced braces (allow 1 off)
            ]
            
            if not all(syntax_checks):
                return {"valid": False, "error": "Invalid TypeScript syntax detected"}
            
            # Check for hallucinated React hooks
            invalid_hooks = [
                'useAutoState', 'useMagic', 'useSuper', 'useAuto', 
                'useAdvanced', 'useEnhanced', 'usePerfect'
            ]
            
            for invalid_hook in invalid_hooks:
                if invalid_hook in code:
                    return {"valid": False, "error": f"Invalid/hallucinated React hook: {invalid_hook}"}
            
            return {"valid": True, "confidence": 0.8}
            
        except Exception as e:
            return {"valid": False, "error": f"Validation error: {str(e)}"}
    
    def _validate_python_code(self, code: str) -> Dict[str, Any]:
        """
        Validate Python code to prevent hallucinated APIs - ANTI-HALLUCINATION
        """
        try:
            # Try to compile the code
            compile(code, '<string>', 'exec')
            
            # Check for suspicious imports that might be hallucinated
            import_lines = [line for line in code.split('\n') if line.strip().startswith('import') or line.strip().startswith('from')]
            
            suspicious_packages = [
                'super_fastapi', 'magic_python', 'auto_api', 
                'enhanced_fastapi', 'perfect_python'
            ]
            
            for import_line in import_lines:
                if any(pkg in import_line.lower() for pkg in suspicious_packages):
                    return {"valid": False, "error": f"Suspicious package in import: {import_line}"}
            
            return {"valid": True, "confidence": 0.9}
            
        except SyntaxError as e:
            return {"valid": False, "error": f"Python syntax error: {str(e)}"}
        except Exception as e:
            return {"valid": False, "error": f"Code validation error: {str(e)}"}