"""
BOWEN Framework - Adaptive Memory Engine
Context-aware learning system that understands your life

This engine builds comprehensive understanding of:
- Academic work (Database Systems, Geology, Business Comm)
- Coding projects (Remi Guardian, FraudZero)
- Business operations (ShipRite, team management)
- Personal goals (75 Hard, career objectives)
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
import yaml

logger = logging.getLogger(__name__)

@dataclass
class ContextMemory:
    """Individual context memory with learning patterns"""
    name: str
    category: str
    concepts: Dict[str, Any]
    patterns: List[str]
    strengths: List[str]
    weaknesses: List[str]
    recent_interactions: List[Dict]
    last_updated: str
    importance_score: float

@dataclass
class LearningInsight:
    """Insights about user's learning patterns"""
    topic: str
    insight: str
    confidence: float
    supporting_evidence: List[str]
    actionable_suggestions: List[str]
    timestamp: str

class AdaptiveMemory:
    """
    Learns from everything you do and builds contextual understanding
    Automatically categorizes and stores knowledge about your life
    """
    
    def __init__(self):
        """Initialize adaptive memory system"""
        self.memory_dir = Path.home() / "Desktop" / "bowen_outputs" / "memory"
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        
        self.contexts_file = self.memory_dir / "contexts.json"
        self.insights_file = self.memory_dir / "insights.json"
        self.profile_file = self.memory_dir / "user_profile.json"
        
        # Initialize context categories based on your life
        self.context_categories = {
            'academic': {
                'database_systems': ContextMemory(
                    name='Database Systems',
                    category='academic',
                    concepts={},
                    patterns=[],
                    strengths=[],
                    weaknesses=['normalization', 'ACID properties'],
                    recent_interactions=[],
                    last_updated=datetime.now().isoformat(),
                    importance_score=0.9  # High - exam today
                ),
                'geology': ContextMemory(
                    name='Geology',
                    category='academic',
                    concepts={},
                    patterns=[],
                    strengths=[],
                    weaknesses=[],
                    recent_interactions=[],
                    last_updated=datetime.now().isoformat(),
                    importance_score=0.7
                ),
                'business_comm': ContextMemory(
                    name='Business Communication',
                    category='academic',
                    concepts={},
                    patterns=[],
                    strengths=[],
                    weaknesses=[],
                    recent_interactions=[],
                    last_updated=datetime.now().isoformat(),
                    importance_score=0.6
                )
            },
            'coding': {
                'remi_guardian': ContextMemory(
                    name='Remi Guardian',
                    category='coding',
                    concepts={'react': {}, 'typescript': {}, 'ui_patterns': {}},
                    patterns=['component_architecture', 'state_management'],
                    strengths=['React components'],
                    weaknesses=['complex state management'],
                    recent_interactions=[],
                    last_updated=datetime.now().isoformat(),
                    importance_score=0.95  # High - active project
                ),
                'fraud_zero': ContextMemory(
                    name='FraudZero',
                    category='coding',
                    concepts={'chrome_extension': {}, 'ai_integration': {}},
                    patterns=['extension_architecture'],
                    strengths=['AI integration'],
                    weaknesses=[],
                    recent_interactions=[],
                    last_updated=datetime.now().isoformat(),
                    importance_score=0.8
                )
            },
            'business': {
                'shiprite': ContextMemory(
                    name='ShipRite',
                    category='business',
                    concepts={'team_management': {}, 'product_strategy': {}},
                    patterns=['leadership_decisions', 'financial_planning'],
                    strengths=['vision', 'execution'],
                    weaknesses=[],
                    recent_interactions=[],
                    last_updated=datetime.now().isoformat(),
                    importance_score=1.0  # Highest - core business
                ),
                'strategy': ContextMemory(
                    name='Strategic Planning',
                    category='business',
                    concepts={'market_analysis': {}, 'competitive_positioning': {}},
                    patterns=[],
                    strengths=[],
                    weaknesses=[],
                    recent_interactions=[],
                    last_updated=datetime.now().isoformat(),
                    importance_score=0.9
                )
            },
            'personal': {
                '75_hard': ContextMemory(
                    name='75 Hard Challenge',
                    category='personal',
                    concepts={'discipline': {}, 'consistency': {}},
                    patterns=['daily_habits'],
                    strengths=['commitment'],
                    weaknesses=['time_management'],
                    recent_interactions=[],
                    last_updated=datetime.now().isoformat(),
                    importance_score=0.8
                ),
                'goals': ContextMemory(
                    name='Life Goals',
                    category='personal',
                    concepts={'career': {}, 'education': {}, 'business': {}},
                    patterns=[],
                    strengths=[],
                    weaknesses=[],
                    recent_interactions=[],
                    last_updated=datetime.now().isoformat(),
                    importance_score=0.9
                )
            }
        }
        
        # Load existing memory or initialize
        self.load_memory()
        
        logger.info("AdaptiveMemory initialized with context-aware learning")
    
    def detect_context(self, interaction: Dict[str, Any]) -> List[str]:
        """
        Automatically detect which contexts apply to this interaction
        
        Args:
            interaction: User interaction data
            
        Returns:
            List of relevant context names
        """
        text = interaction.get('text', '').lower()
        contexts = []
        
        # Academic context detection
        academic_keywords = {
            'database_systems': ['database', 'sql', 'normalization', 'acid', 'dbms', 'relational', 'schema'],
            'geology': ['rock', 'mineral', 'sediment', 'igneous', 'metamorphic', 'geology', 'earth'],
            'business_comm': ['essay', 'writing', 'communication', 'presentation', 'professional']
        }
        
        # Coding context detection
        coding_keywords = {
            'remi_guardian': ['remi', 'react', 'typescript', 'component', 'ui', 'frontend'],
            'fraud_zero': ['fraud', 'chrome', 'extension', 'phishing', 'security']
        }
        
        # Business context detection
        business_keywords = {
            'shiprite': ['shiprite', 'team', 'salary', 'abayomi', 'business', 'company'],
            'strategy': ['strategy', 'planning', 'market', 'competitive', 'growth']
        }
        
        # Personal context detection
        personal_keywords = {
            '75_hard': ['workout', 'exercise', '75 hard', 'discipline', 'habits'],
            'goals': ['goal', 'deadline', 'priority', 'objective', 'achievement']
        }
        
        all_keywords = {
            **academic_keywords,
            **coding_keywords,
            **business_keywords,
            **personal_keywords
        }
        
        # Check for keyword matches
        for context_name, keywords in all_keywords.items():
            if any(keyword in text for keyword in keywords):
                contexts.append(context_name)
        
        # Default to general if no specific context detected
        if not contexts:
            contexts = ['general']
        
        return contexts
    
    def learn_from_interaction(self, interaction: Dict[str, Any]) -> None:
        """
        Learn from user interaction and update relevant contexts
        
        Args:
            interaction: User interaction with text, type, outcome, etc.
        """
        try:
            # Detect relevant contexts
            relevant_contexts = self.detect_context(interaction)
            
            # Update each relevant context
            for context_name in relevant_contexts:
                if context_name != 'general':
                    self.update_context_memory(context_name, interaction)
            
            # Extract learning insights
            insights = self.extract_insights(interaction, relevant_contexts)
            for insight in insights:
                self.store_insight(insight)
            
            # Save updated memory
            self.save_memory()
            
            logger.info(f"Learned from interaction, updated contexts: {relevant_contexts}")
            
        except Exception as e:
            logger.error(f"Failed to learn from interaction: {e}")
    
    def update_context_memory(self, context_name: str, interaction: Dict[str, Any]) -> None:
        """Update specific context with new interaction"""
        # Find the context across all categories
        context = None
        for category in self.context_categories.values():
            if context_name in category:
                context = category[context_name]
                break
        
        if not context:
            return
        
        # Add to recent interactions
        context.recent_interactions.append({
            'timestamp': datetime.now().isoformat(),
            'text': interaction.get('text', ''),
            'type': interaction.get('type', 'unknown'),
            'outcome': interaction.get('outcome', 'unknown')
        })
        
        # Keep only recent interactions (last 20)
        context.recent_interactions = context.recent_interactions[-20:]
        
        # Update last updated
        context.last_updated = datetime.now().isoformat()
        
        # Analyze for patterns, strengths, weaknesses
        self.analyze_context_patterns(context, interaction)
    
    def analyze_context_patterns(self, context: ContextMemory, interaction: Dict[str, Any]) -> None:
        """Analyze interaction for learning patterns"""
        text = interaction.get('text', '').lower()
        outcome = interaction.get('outcome', '')
        
        # Pattern detection based on context category
        if context.category == 'academic':
            if 'help' in text or 'explain' in text:
                if 'understand' in outcome.lower():
                    # User understood after explanation
                    if interaction.get('topic') not in context.strengths:
                        context.strengths.append(interaction.get('topic', 'general'))
                else:
                    # User still struggling
                    if interaction.get('topic') not in context.weaknesses:
                        context.weaknesses.append(interaction.get('topic', 'general'))
        
        elif context.category == 'coding':
            if 'error' in text or 'bug' in text:
                context.patterns.append(f"debugging_{interaction.get('language', 'unknown')}")
            if 'create' in text or 'build' in text:
                context.patterns.append(f"development_{interaction.get('feature', 'unknown')}")
    
    def extract_insights(self, interaction: Dict[str, Any], contexts: List[str]) -> List[LearningInsight]:
        """Extract learning insights from interaction"""
        insights = []
        
        # Academic insights
        if any(c in ['database_systems', 'geology', 'business_comm'] for c in contexts):
            if 'struggling' in interaction.get('text', '').lower():
                insights.append(LearningInsight(
                    topic=contexts[0],
                    insight="User needs additional support in this subject",
                    confidence=0.8,
                    supporting_evidence=[interaction.get('text', '')],
                    actionable_suggestions=["Schedule focused study time", "Create practice problems", "Review fundamentals"],
                    timestamp=datetime.now().isoformat()
                ))
        
        # Coding insights
        if any(c in ['remi_guardian', 'fraud_zero'] for c in contexts):
            if 'error' in interaction.get('text', '').lower():
                insights.append(LearningInsight(
                    topic=contexts[0],
                    insight="Recurring debugging pattern detected",
                    confidence=0.7,
                    supporting_evidence=[interaction.get('text', '')],
                    actionable_suggestions=["Create debugging checklist", "Set up better error handling"],
                    timestamp=datetime.now().isoformat()
                ))
        
        return insights
    
    def store_insight(self, insight: LearningInsight) -> None:
        """Store learning insight"""
        insights = self.load_insights()
        insights.append(asdict(insight))
        
        with open(self.insights_file, 'w') as f:
            json.dump(insights, f, indent=2)
    
    def get_context_summary(self, context_name: str) -> Dict[str, Any]:
        """Get comprehensive summary of specific context"""
        # Find context
        context = None
        for category in self.context_categories.values():
            if context_name in category:
                context = category[context_name]
                break
        
        if not context:
            return {}
        
        return {
            'name': context.name,
            'category': context.category,
            'strengths': context.strengths,
            'weaknesses': context.weaknesses,
            'recent_patterns': context.patterns[-5:],
            'importance': context.importance_score,
            'last_activity': context.last_updated,
            'interaction_count': len(context.recent_interactions)
        }
    
    def get_current_priorities(self) -> List[Dict[str, Any]]:
        """Get current priority contexts based on importance and activity"""
        all_contexts = []
        
        for category_name, category in self.context_categories.items():
            for context_name, context in category.items():
                all_contexts.append({
                    'name': context.name,
                    'context_key': context_name,
                    'category': context.category,
                    'importance': context.importance_score,
                    'last_updated': context.last_updated,
                    'weaknesses': len(context.weaknesses),
                    'recent_activity': len(context.recent_interactions)
                })
        
        # Sort by importance and recent activity
        all_contexts.sort(key=lambda x: (x['importance'], x['recent_activity']), reverse=True)
        
        return all_contexts[:10]  # Top 10 priorities
    
    def generate_learning_report(self) -> str:
        """Generate comprehensive learning report"""
        priorities = self.get_current_priorities()
        insights = self.load_insights()
        
        report = "📊 **ADAPTIVE MEMORY REPORT**\n\n"
        
        # Current priorities
        report += "🎯 **Current Priorities:**\n"
        for i, context in enumerate(priorities[:5], 1):
            report += f"{i}. **{context['name']}** (Importance: {context['importance']:.1f})\n"
            if context['weaknesses'] > 0:
                report += f"   ⚠️ {context['weaknesses']} areas needing attention\n"
        
        report += "\n"
        
        # Recent insights
        recent_insights = insights[-5:] if insights else []
        if recent_insights:
            report += "💡 **Recent Learning Insights:**\n"
            for insight in recent_insights:
                report += f"• **{insight['topic']}**: {insight['insight']}\n"
        
        return report
    
    def save_memory(self) -> None:
        """Save memory to disk"""
        try:
            # Convert contexts to serializable format
            serializable_contexts = {}
            for category_name, category in self.context_categories.items():
                serializable_contexts[category_name] = {}
                for context_name, context in category.items():
                    serializable_contexts[category_name][context_name] = asdict(context)
            
            with open(self.contexts_file, 'w') as f:
                json.dump(serializable_contexts, f, indent=2)
                
        except Exception as e:
            logger.error(f"Failed to save memory: {e}")
    
    def load_memory(self) -> None:
        """Load memory from disk"""
        try:
            if self.contexts_file.exists():
                with open(self.contexts_file, 'r') as f:
                    data = json.load(f)
                
                # Convert back to ContextMemory objects
                for category_name, category_data in data.items():
                    if category_name in self.context_categories:
                        for context_name, context_data in category_data.items():
                            self.context_categories[category_name][context_name] = ContextMemory(**context_data)
                            
        except Exception as e:
            logger.warning(f"Failed to load existing memory, starting fresh: {e}")
    
    def load_insights(self) -> List[Dict]:
        """Load insights from disk"""
        try:
            if self.insights_file.exists():
                with open(self.insights_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load insights: {e}")
        
        return []