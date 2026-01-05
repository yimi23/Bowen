# 🛡️ BOWEN ANTI-HALLUCINATION PROTOCOL

## 🚨 **CRITICAL RULE: NEVER ASK CLAUDE FOR FACTS**

### ❌ **BAD (CAUSES HALLUCINATION):**
```python
# Don't ask Claude for factual information
response = claude.ask("What Claude models are available?")
response = claude.ask("What files are in this directory?") 
response = claude.ask("What time is it?")
response = claude.ask("What's the latest React version?")
```

### ✅ **GOOD (USES REAL DATA):**
```python
# Query actual APIs and tools
models = requests.get("https://api.anthropic.com/v1/models").json()
files = os.listdir(directory_path)
current_time = datetime.now()
react_version = requests.get("https://api.npmjs.com/packages/react").json()
```

## 🎯 **ANTI-HALLUCINATION ARCHITECTURE**

### 1. **TOOL-FIRST APPROACH**
Always use tools before asking Claude:

```python
def get_real_data(query_type: str, params: dict):
    """Get factual data using tools, NOT Claude"""
    
    if query_type == "file_content":
        # Read actual file
        with open(params['path'], 'r') as f:
            return f.read()
    
    elif query_type == "directory_listing":
        # List actual directory
        return os.listdir(params['path'])
    
    elif query_type == "api_models":
        # Query actual API
        response = requests.get("https://api.anthropic.com/v1/models")
        return response.json()
    
    elif query_type == "current_time":
        # Get system time
        return datetime.now().isoformat()
    
    elif query_type == "git_status":
        # Run actual git command
        result = subprocess.run(['git', 'status'], capture_output=True, text=True)
        return result.stdout
    
    # Always use tools first, Claude second
```

### 2. **VALIDATION LAYER**
Validate all Claude outputs:

```python
def validate_claude_output(output: str, expected_type: str) -> bool:
    """Validate Claude's response"""
    
    if expected_type == "json":
        try:
            json.loads(output)
            return True
        except:
            return False
    
    elif expected_type == "python_code":
        try:
            compile(output, '<string>', 'exec')
            return True
        except SyntaxError:
            return False
    
    elif expected_type == "file_path":
        return os.path.exists(output)
    
    elif expected_type == "url":
        try:
            response = requests.head(output, timeout=5)
            return response.status_code == 200
        except:
            return False
    
    return False

def safe_claude_call(prompt: str, expected_type: str = None):
    """Claude call with validation"""
    response = claude.ask(prompt)
    
    if expected_type and not validate_claude_output(response, expected_type):
        return {"error": "Claude response failed validation", "response": response}
    
    return {"success": True, "response": response}
```

### 3. **GROUNDING IN REAL DATA**
Ground all responses in verifiable facts:

```python
def grounded_response(claim: str, evidence: dict) -> str:
    """Only make claims backed by evidence"""
    
    if not evidence:
        return "I don't have verified information about that."
    
    # Include evidence in response
    response = f"{claim}\n\n"
    response += "**Evidence:**\n"
    
    for source, data in evidence.items():
        response += f"• {source}: {data['value']} (verified {data['timestamp']})\n"
    
    return response

# Example usage:
def get_team_status():
    """Get team status grounded in real memory"""
    
    memory = load_memory_file()  # Real file
    evidence = {}
    
    if 'team_updates' in memory:
        evidence['memory'] = {
            'value': memory['team_updates'],
            'timestamp': memory['last_updated']
        }
    
    if evidence:
        return grounded_response("Your team is working on...", evidence)
    else:
        return "I don't have current team status. What updates do you have?"
```

### 4. **CONFIDENCE SCORING**
Make Claude admit uncertainty:

```python
def confident_response(question: str) -> dict:
    """Get response with confidence scoring"""
    
    prompt = f"""
    {question}
    
    Provide your answer and confidence level (0-1):
    {{
        "answer": "your answer here",
        "confidence": 0.8,
        "reasoning": "why you're confident/uncertain"
    }}
    """
    
    response = claude.ask(prompt)
    parsed = json.loads(response)
    
    if parsed['confidence'] < 0.7:
        # Low confidence - research instead
        return {
            "answer": "I'm not confident about this. Let me research it.",
            "action": "research_needed",
            "confidence": parsed['confidence']
        }
    
    return parsed
```

### 5. **STRUCTURED OUTPUTS**
Force structured responses to prevent hallucination:

```python
def structured_extraction(text: str, schema: dict) -> dict:
    """Extract structured data with validation"""
    
    prompt = f"""
    Extract information from this text according to the exact schema.
    Return ONLY valid JSON matching this schema:
    
    Schema: {json.dumps(schema, indent=2)}
    
    Text: {text}
    
    CRITICAL: If information is not explicitly in the text, use null.
    Do NOT infer or guess.
    """
    
    response = claude.ask(prompt)
    
    try:
        data = json.loads(response)
        # Validate against schema
        if validate_schema(data, schema):
            return data
        else:
            return {"error": "Response doesn't match schema"}
    except:
        return {"error": "Invalid JSON response"}
```

## 🔧 **IMPLEMENTED FIXES**

### ✅ **Fixed: Self-Upgrader Model Detection**

**BEFORE (Hallucination Risk):**
```python
# Asked Claude what models exist
response = claude.ask("What Claude models are available?")
# Claude invents: "claude-sonnet-5-20260115"
```

**AFTER (Real API Testing):**
```python
def _get_available_models(self):
    """Test real models by calling Anthropic API"""
    known_models = [
        "claude-3-haiku-20240307",
        "claude-3-5-sonnet-20241022",
        # Only real model names
    ]
    
    available = []
    for model in known_models:
        try:
            # Actually test if model works
            response = self.client.messages.create(
                model=model,
                max_tokens=10,
                messages=[{"role": "user", "content": "test"}]
            )
            available.append(model)  # Only if API call succeeds
        except:
            pass  # Model doesn't exist
    
    return available
```

### 🎯 **To Fix Next:**

1. **Research Engine** - Validate web search results
2. **Code Generation** - Compile and test generated code
3. **Memory System** - Only cite facts user actually told BOWEN
4. **Document Creation** - Verify citations and sources

## 📋 **ANTI-HALLUCINATION CHECKLIST**

For every BOWEN response:

- [ ] **Facts verified** through tools/APIs (not Claude)
- [ ] **Sources cited** with timestamps where applicable  
- [ ] **Uncertainty admitted** when confidence < 70%
- [ ] **Structured outputs** used for data extraction
- [ ] **Validation performed** on all Claude responses
- [ ] **Real data grounding** - claims backed by evidence
- [ ] **Cross-reference** important facts across sources

## 🚨 **EMERGENCY PROTOCOL**

If Claude makes an unverified claim:
1. **Stop immediately** 
2. **Research the claim** using tools
3. **Validate against real sources**
4. **Correct the record** if wrong
5. **Update anti-hallucination filters**

## 🎯 **SUCCESS METRICS**

- **Zero invented facts** (all claims verifiable)
- **High tool usage** (tools before Claude for facts)
- **Source attribution** (every fact has a source)
- **Uncertainty admission** (confidence scores < 70% flagged)
- **Validation passing** (all outputs pass validation)

---

**The fundamental rule: If Claude can't verify it with tools, BOWEN doesn't claim it.** 🛡️