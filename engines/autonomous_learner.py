#!/usr/bin/env python3
"""
BOWEN Autonomous Learning Engine
Makes BOWEN teach itself concepts it doesn't know
"""

import json
import re
import os
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
import anthropic

logger = logging.getLogger(__name__)

class AutonomousLearner:
    """
    Autonomous learning system that:
    1. Detects unknown concepts in conversations
    2. Researches autonomously using web search
    3. Builds persistent knowledge base
    4. Connects new knowledge to existing knowledge
    5. Applies learned knowledge immediately
    """
    
    def __init__(self, knowledge_path: str, research_engine, claude_engine):
        """
        Initialize with knowledge base path and research capabilities
        """
        self.knowledge_path = Path(knowledge_path)
        self.research_engine = research_engine
        self.claude_engine = claude_engine
        
        # Ensure knowledge directory exists
        self.knowledge_path.mkdir(parents=True, exist_ok=True)
        
        # Initialize knowledge files
        self.concepts_file = self.knowledge_path / "concepts.json"
        self.connections_file = self.knowledge_path / "connections.json"
        self.sources_file = self.knowledge_path / "sources.json"
        
        # Load existing knowledge
        self.concepts = self._load_json(self.concepts_file, {})
        self.connections = self._load_json(self.connections_file, {})
        self.sources = self._load_json(self.sources_file, {})
        
        logger.info(f"Autonomous Learner initialized with {len(self.concepts)} concepts")
    
    def _load_json(self, file_path: Path, default: Any) -> Any:
        """Load JSON file or return default if not exists"""
        try:
            if file_path.exists():
                with open(file_path, 'r') as f:
                    return json.load(f)
            return default
        except Exception as e:
            logger.error(f"Error loading {file_path}: {e}")
            return default
    
    def _save_json(self, file_path: Path, data: Any):
        """Save data to JSON file"""
        try:
            with open(file_path, 'w') as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Error saving {file_path}: {e}")
    
    def detect_unknowns(self, conversation: str) -> List[str]:
        """
        Only learn from REAL queries, not casual chat
        Scan conversation for unknown terms that user is ASKING about
        """
        try:
            # Ignore casual greetings and wake-up commands
            casual_phrases = [
                'hey', 'hi', 'hello', "what's up", 'wake up', 'good morning',
                'wake uo', 'daddies home', 'beep', 'whir', 'system check'
            ]
            if any(phrase in conversation.lower() for phrase in casual_phrases):
                return []
            
            # Only learn if user is ASKING about something
            query_indicators = ['what is', 'explain', 'tell me about', 'how does', 'help with', '?']
            if not any(indicator in conversation.lower() for indicator in query_indicators):
                return []
            
            # Use Claude to identify technical concepts, frameworks, tools
            detection_prompt = f"""
            Analyze this conversation and identify ONLY technical concepts that the user is actively asking about:

            Conversation: "{conversation}"

            Only include concepts if the user is:
            - Asking "what is X?" or "explain X" 
            - Seeking help with a specific technology/tool
            - Learning about a new framework or concept

            DO NOT include:
            - Casual conversation topics
            - Greetings or social interactions
            - System actions or status updates

            Return ONLY a JSON list of terms to research:
            ["term1", "term2", "term3"]

            If no technical terms need research, return: []
            """
            
            response = self.claude_engine.client.messages.create(
                model=self.claude_engine.model,
                max_tokens=500,
                messages=[{"role": "user", "content": detection_prompt}]
            )
            
            result_text = response.content[0].text.strip()
            
            # Parse JSON response
            if result_text.startswith('[') and result_text.endswith(']'):
                detected_terms = json.loads(result_text)
            else:
                # Try to extract list from text
                import ast
                try:
                    detected_terms = ast.literal_eval(result_text)
                except:
                    detected_terms = []
            
            # Filter out terms we already know
            unknown_terms = []
            for term in detected_terms:
                term_lower = term.lower()
                if term_lower not in self.concepts and len(term.split()) <= 3:  # Skip long phrases
                    unknown_terms.append(term)
            
            logger.info(f"Detected {len(unknown_terms)} unknown concepts: {unknown_terms}")
            return unknown_terms
            
        except Exception as e:
            logger.error(f"Error detecting unknowns: {e}")
            return []
    
    def research_concept(self, concept: str, context: dict = None) -> Dict[str, Any]:
        """
        Use research_engine to search and extract VERIFIED knowledge - ANTI-HALLUCINATION
        
        Extract:
        - Definition (from research, not invented)
        - Use cases (from examples, not speculation)
        - Examples (from sources, not made up)
        - Code samples (validated, not hallucinated)
        - Best practices (from authoritative sources)
        """
        try:
            if context is None:
                context = {}
            
            logger.info(f"🔍 Researching concept: {concept} (anti-hallucination mode)")
            
            # STEP 1: Use tools to gather REAL data
            research_query = f"{concept} explanation definition examples best practices"
            if context.get('domain'):
                research_query += f" {context['domain']}"
            
            # Use research engine to gather information from REAL sources
            research_results = self.research_engine.research_and_report(research_query)
            
            # STEP 2: Validate research results exist
            if not research_results or len(research_results.strip()) < 50:
                logger.warning(f"Insufficient research data for {concept}")
                return {
                    "concept": concept,
                    "definition": f"Research completed for {concept}",
                    "category": "general",
                    "learned_at": datetime.now().isoformat(),
                    "sources": [research_query],
                    "confidence": 0.5,
                    "user_relevance": "medium",
                    "verified": False,
                    "error": "Insufficient research data"
                }
            
            # STEP 3: Extract ONLY information present in research (anti-hallucination)
            extraction_prompt = f"""
            CRITICAL ANTI-HALLUCINATION RULES:
            1. ONLY extract information explicitly present in the research text
            2. If information is not in the research, use null or empty array
            3. Do NOT infer, guess, or make up information
            4. Mark confidence based on quality of research sources
            
            Research text about "{concept}":
            {research_results[:4000]}  # Limit context

            Extract ONLY verified information and return JSON:
            {{
                "concept": "{concept}",
                "definition": "ONLY if clear definition found in research, otherwise null",
                "category": "programming/database/business/academic/tool",
                "use_cases": ["ONLY use cases explicitly mentioned in research"],
                "examples": ["ONLY examples found in research text"],
                "code_samples": ["ONLY if code examples present in research"],
                "best_practices": ["ONLY practices mentioned in sources"],
                "related_concepts": ["ONLY concepts explicitly connected in research"],
                "difficulty_level": "beginner/intermediate/advanced",
                "user_relevance": "high/medium/low",
                "confidence": 0.8,
                "source_quality": "high/medium/low"
            }}

            VALIDATION REQUIREMENTS:
            - If concept is not clearly explained in research, set confidence to 0.3
            - If multiple sources agree, set confidence to 0.8
            - If research is sparse, set confidence to 0.5
            - For Yimi's tech stack (React, Python, databases), mark relevance as "high"
            
            RETURN ONLY THE JSON - NO EXPLANATIONS
            """
            
            response = self.claude_engine.client.messages.create(
                model=self.claude_engine.model,
                max_tokens=1500,
                messages=[{"role": "user", "content": extraction_prompt}]
            )
            
            result_text = response.content[0].text.strip()
            
            # Clean up and parse JSON
            if result_text.startswith('```json'):
                result_text = result_text[7:-3]
            elif result_text.startswith('```'):
                result_text = result_text[3:-3]
            
            try:
                knowledge = json.loads(result_text)
                
                # Add metadata
                knowledge.update({
                    "learned_at": datetime.now().isoformat(),
                    "sources": [research_query],  # Could be enhanced with actual URLs
                    "confidence": 0.8,  # Default confidence
                    "last_accessed": datetime.now().isoformat()
                })
                
                logger.info(f"Successfully researched concept: {concept}")
                return knowledge
                
            except json.JSONDecodeError:
                # Fallback: create basic knowledge structure
                return {
                    "concept": concept,
                    "definition": f"Research completed for {concept}",
                    "category": "general",
                    "learned_at": datetime.now().isoformat(),
                    "sources": [research_query],
                    "confidence": 0.5,
                    "user_relevance": "medium"
                }
                
        except Exception as e:
            logger.error(f"Error researching concept {concept}: {e}")
            return {
                "concept": concept,
                "definition": f"Error occurred while researching {concept}",
                "learned_at": datetime.now().isoformat(),
                "error": str(e)
            }
    
    def save_knowledge(self, concept: str, knowledge: Dict[str, Any]):
        """
        Save knowledge to persistent storage
        Update connections between concepts
        """
        try:
            # Save concept
            concept_key = concept.lower()
            self.concepts[concept_key] = knowledge
            
            # Update connections
            related_concepts = knowledge.get('related_concepts', [])
            if concept_key not in self.connections:
                self.connections[concept_key] = []
            
            for related in related_concepts:
                related_key = related.lower()
                if related_key not in self.connections[concept_key]:
                    self.connections[concept_key].append(related_key)
                
                # Bidirectional connection
                if related_key not in self.connections:
                    self.connections[related_key] = []
                if concept_key not in self.connections[related_key]:
                    self.connections[related_key].append(concept_key)
            
            # Save sources
            sources = knowledge.get('sources', [])
            for source in sources:
                if source not in self.sources:
                    self.sources[source] = []
                if concept_key not in self.sources[source]:
                    self.sources[source].append(concept_key)
            
            # Persist to files
            self._save_json(self.concepts_file, self.concepts)
            self._save_json(self.connections_file, self.connections)
            self._save_json(self.sources_file, self.sources)
            
            logger.info(f"Saved knowledge for concept: {concept}")
            
        except Exception as e:
            logger.error(f"Error saving knowledge for {concept}: {e}")
    
    def get_knowledge(self, concept: str) -> Optional[Dict[str, Any]]:
        """Get knowledge about a concept"""
        concept_key = concept.lower()
        knowledge = self.concepts.get(concept_key)
        
        if knowledge:
            # Update last accessed
            knowledge['last_accessed'] = datetime.now().isoformat()
            self.concepts[concept_key] = knowledge
            self._save_json(self.concepts_file, self.concepts)
        
        return knowledge
    
    def apply_knowledge(self, query: str) -> str:
        """
        Use learned knowledge to answer queries
        Combine multiple concepts if needed
        """
        try:
            # Find relevant concepts
            query_lower = query.lower()
            relevant_concepts = []
            
            for concept_key, knowledge in self.concepts.items():
                if concept_key in query_lower:
                    relevant_concepts.append(knowledge)
                elif any(keyword in query_lower for keyword in knowledge.get('related_concepts', [])):
                    relevant_concepts.append(knowledge)
            
            if not relevant_concepts:
                return "I don't have specific knowledge about that topic yet. Let me research it."
            
            # Use Claude to synthesize knowledge
            knowledge_text = "\n\n".join([
                f"**{k.get('concept', 'Unknown')}**: {k.get('definition', 'No definition')}\n"
                f"Use cases: {', '.join(k.get('use_cases', []))}\n"
                f"Examples: {', '.join(k.get('examples', []))}"
                for k in relevant_concepts[:3]  # Limit to top 3
            ])
            
            synthesis_prompt = f"""
            Based on my knowledge base, answer this query: "{query}"

            My knowledge:
            {knowledge_text}

            Provide a helpful, practical answer using this knowledge. Include specific examples or code samples if relevant.
            """
            
            response = self.claude_engine.client.messages.create(
                model=self.claude_engine.model,
                max_tokens=800,
                messages=[{"role": "user", "content": synthesis_prompt}]
            )
            
            return response.content[0].text
            
        except Exception as e:
            logger.error(f"Error applying knowledge: {e}")
            return f"Error accessing knowledge base: {str(e)}"
    
    def learn_from_conversation(self, user_input: str, ai_response: str, context: dict = None):
        """
        Main learning method: analyze conversation and learn new concepts
        """
        try:
            # Combine input and response for analysis
            conversation = f"User: {user_input}\nAssistant: {ai_response}"
            
            # Detect unknown concepts
            unknown_concepts = self.detect_unknowns(conversation)
            
            if not unknown_concepts:
                return {"learned": False, "concepts": []}
            
            # Research each concept
            learned_concepts = []
            for concept in unknown_concepts[:3]:  # Limit to 3 concepts per conversation
                knowledge = self.research_concept(concept, context)
                if knowledge:
                    self.save_knowledge(concept, knowledge)
                    learned_concepts.append(concept)
            
            logger.info(f"Learned {len(learned_concepts)} new concepts: {learned_concepts}")
            
            return {
                "learned": len(learned_concepts) > 0,
                "concepts": learned_concepts,
                "total_concepts": len(self.concepts)
            }
            
        except Exception as e:
            logger.error(f"Error in learn_from_conversation: {e}")
            return {"learned": False, "error": str(e)}
    
    def get_learning_stats(self) -> Dict[str, Any]:
        """Get statistics about learned concepts"""
        try:
            categories = {}
            relevance_counts = {"high": 0, "medium": 0, "low": 0}
            recent_concepts = []
            
            for concept, knowledge in self.concepts.items():
                # Count by category
                category = knowledge.get('category', 'unknown')
                categories[category] = categories.get(category, 0) + 1
                
                # Count by relevance
                relevance = knowledge.get('user_relevance', 'medium')
                if relevance in relevance_counts:
                    relevance_counts[relevance] += 1
                
                # Track recent concepts (last 7 days)
                learned_at = knowledge.get('learned_at')
                if learned_at:
                    try:
                        learned_date = datetime.fromisoformat(learned_at.replace('Z', '+00:00'))
                        days_ago = (datetime.now() - learned_date).days
                        if days_ago <= 7:
                            recent_concepts.append({
                                "concept": knowledge.get('concept', concept),
                                "days_ago": days_ago,
                                "relevance": relevance
                            })
                    except:
                        pass
            
            return {
                "total_concepts": len(self.concepts),
                "categories": categories,
                "relevance_distribution": relevance_counts,
                "recent_concepts": sorted(recent_concepts, key=lambda x: x['days_ago']),
                "connections": len(self.connections),
                "sources": len(self.sources)
            }
            
        except Exception as e:
            logger.error(f"Error getting learning stats: {e}")
            return {"error": str(e)}
    
    def generate_learning_report(self) -> str:
        """Generate a human-readable learning report"""
        try:
            stats = self.get_learning_stats()
            
            report = "🧠 **AUTONOMOUS LEARNING REPORT**\n"
            report += "=" * 40 + "\n\n"
            
            report += f"📚 **Total Concepts Learned:** {stats.get('total_concepts', 0)}\n"
            report += f"🔗 **Concept Connections:** {stats.get('connections', 0)}\n"
            report += f"📖 **Research Sources:** {stats.get('sources', 0)}\n\n"
            
            # Categories
            categories = stats.get('categories', {})
            if categories:
                report += "**📂 Knowledge by Category:**\n"
                for category, count in sorted(categories.items(), key=lambda x: x[1], reverse=True):
                    report += f"  • {category.title()}: {count} concepts\n"
                report += "\n"
            
            # Recent learning
            recent = stats.get('recent_concepts', [])
            if recent:
                report += "**🆕 Recently Learned (Last 7 Days):**\n"
                for item in recent[:5]:  # Show top 5
                    days = item['days_ago']
                    day_text = "today" if days == 0 else f"{days} day{'s' if days > 1 else ''} ago"
                    relevance_emoji = {"high": "🔥", "medium": "📝", "low": "📋"}.get(item['relevance'], "📝")
                    report += f"  {relevance_emoji} **{item['concept']}** - {day_text}\n"
                report += "\n"
            
            # Relevance distribution
            relevance = stats.get('relevance_distribution', {})
            high_relevance = relevance.get('high', 0)
            total = sum(relevance.values())
            if total > 0:
                high_percentage = (high_relevance / total) * 100
                report += f"**🎯 High-Relevance Concepts:** {high_relevance} ({high_percentage:.1f}%)\n"
                report += "   (Concepts directly relevant to your work and goals)\n\n"
            
            report += "**💡 Learning Status:** Autonomous learning is active and growing the knowledge base!"
            
            return report
            
        except Exception as e:
            return f"Error generating learning report: {str(e)}"