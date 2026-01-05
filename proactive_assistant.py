"""
BOWEN Framework - Proactive Assistant Engine
Doesn't wait for you to ask - tells YOU what to do

Provides:
- Morning briefings with priorities
- Deadline tracking and alerts  
- Progress monitoring
- Intelligent reminders
- Context-aware suggestions
"""

import json
import logging
from datetime import datetime, timedelta, time
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
import calendar

logger = logging.getLogger(__name__)

@dataclass
class Deadline:
    """Tracked deadline with priority and status"""
    name: str
    due_date: datetime
    category: str
    priority: float  # 0.0 to 1.0
    description: str
    status: str  # 'pending', 'in_progress', 'completed', 'overdue'
    estimated_hours: float
    progress: float  # 0.0 to 1.0
    reminders: List[datetime]

@dataclass
class Goal:
    """Personal or professional goal with tracking"""
    name: str
    category: str
    target_date: datetime
    description: str
    progress: float
    milestones: List[Dict]
    daily_requirement: Optional[str]
    streak: int
    last_completed: Optional[datetime]

@dataclass
class Alert:
    """Proactive alert or reminder"""
    message: str
    priority: str  # 'low', 'medium', 'high', 'critical'
    category: str
    action_required: bool
    deadline: Optional[datetime]
    created: datetime

class ProactiveAssistant:
    """
    Intelligent assistant that proactively manages your life
    Tracks everything and tells you what needs attention
    """
    
    def __init__(self):
        """Initialize proactive assistant"""
        self.data_dir = Path.home() / "Desktop" / "bowen_outputs" / "proactive"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.deadlines_file = self.data_dir / "deadlines.json"
        self.goals_file = self.data_dir / "goals.json"
        self.alerts_file = self.data_dir / "alerts.json"
        self.schedule_file = self.data_dir / "schedule.json"
        
        # Initialize your current deadlines and goals
        self.deadlines = self.load_deadlines()
        self.goals = self.load_goals()
        self.alerts = []
        
        # Initialize with your known deadlines and goals
        self.initialize_your_life()
        
        logger.info("ProactiveAssistant initialized with intelligent monitoring")
    
    def initialize_your_life(self) -> None:
        """Initialize with your known deadlines and goals"""
        current_deadlines = {
            'database_exam': Deadline(
                name='Database Systems Exam',
                due_date=datetime(2025, 1, 1, 14, 0),  # Today at 2pm
                category='academic',
                priority=0.95,
                description='Database Systems final exam - normalization weakness identified',
                status='pending',
                estimated_hours=2.0,
                progress=0.8,  # 80% studied
                reminders=[]
            ),
            'depaul_application': Deadline(
                name='DePaul University Application',
                due_date=datetime(2025, 1, 16),  # 15 days from now
                category='academic',
                priority=0.9,
                description='Graduate school application with essay requirement',
                status='in_progress',
                estimated_hours=20.0,
                progress=0.3,  # Essay partially done
                reminders=[]
            ),
            'remi_whiteboard': Deadline(
                name='Remi Guardian Whiteboard Feature',
                due_date=datetime(2025, 2, 1),  # 32 days (launch target)
                category='coding',
                priority=0.95,
                description='Critical feature for Remi Guardian launch',
                status='in_progress',
                estimated_hours=40.0,
                progress=0.6,  # 60% complete based on your estimate
                reminders=[]
            ),
            'abayomi_salary': Deadline(
                name='Abayomi Salary Payment',
                due_date=datetime(2025, 1, 3),  # 2 days from now
                category='business',
                priority=1.0,
                description='Team member salary payment',
                status='pending',
                estimated_hours=0.5,
                progress=0.0,
                reminders=[]
            )
        }
        
        current_goals = {
            '75_hard': Goal(
                name='75 Hard Challenge',
                category='personal',
                target_date=datetime(2025, 3, 15),  # 75 days from start
                description='Complete 75 Hard mental toughness challenge',
                progress=24/75,  # Day 24
                milestones=[
                    {'day': 25, 'description': 'First milestone - persistence building'},
                    {'day': 50, 'description': 'Halfway point'},
                    {'day': 75, 'description': 'Challenge complete'}
                ],
                daily_requirement='Workout, read 10 pages, drink water, take photo',
                streak=24,
                last_completed=datetime(2024, 12, 30)  # Yesterday
            ),
            'graduation': Goal(
                name='University Graduation',
                category='academic',
                target_date=datetime(2025, 5, 15),  # Expected graduation
                description='Complete all coursework and graduate',
                progress=0.85,  # Senior year
                milestones=[
                    {'semester': 'current', 'description': 'Pass all current classes'},
                    {'semester': 'final', 'description': 'Complete final semester'}
                ],
                daily_requirement=None,
                streak=0,
                last_completed=None
            ),
            'shiprite_growth': Goal(
                name='ShipRite Business Growth',
                category='business',
                target_date=datetime(2025, 12, 31),
                description='Scale ShipRite to sustainable profitability',
                progress=0.4,
                milestones=[
                    {'quarter': 'Q1', 'description': 'Launch Remi Guardian'},
                    {'quarter': 'Q2', 'description': 'User acquisition milestone'},
                    {'quarter': 'Q3', 'description': 'Revenue targets'}
                ],
                daily_requirement='Strategic work on core products',
                streak=0,
                last_completed=None
            )
        }
        
        # Only add if not already loaded
        if not self.deadlines:
            self.deadlines = current_deadlines
            self.save_deadlines()
        
        if not self.goals:
            self.goals = current_goals
            self.save_goals()
    
    def generate_morning_briefing(self) -> str:
        """Generate comprehensive morning briefing"""
        now = datetime.now()
        
        briefing = f"🌅 **GOOD MORNING, PRAISE** - {now.strftime('%A, %B %d, %Y')}\n"
        briefing += "=" * 60 + "\n\n"
        
        # Today's critical items
        briefing += "🎯 **TODAY'S PRIORITIES:**\n"
        today_items = self.get_todays_priorities()
        for i, item in enumerate(today_items, 1):
            briefing += f"{i}. **{item['name']}** ({item['category']})\n"
            if item.get('time'):
                briefing += f"   ⏰ {item['time']}\n"
            if item.get('status'):
                briefing += f"   📊 Status: {item['status']}\n"
        
        briefing += "\n"
        
        # Urgent deadlines
        urgent_deadlines = self.get_urgent_deadlines()
        if urgent_deadlines:
            briefing += "⚠️ **URGENT DEADLINES:**\n"
            for deadline in urgent_deadlines:
                days_left = (deadline.due_date - now).days
                briefing += f"• **{deadline.name}**: {days_left} days left ({deadline.progress*100:.0f}% complete)\n"
            briefing += "\n"
        
        # Progress updates
        briefing += "📈 **PROGRESS UPDATES:**\n"
        progress = self.get_progress_summary()
        for item in progress:
            briefing += f"• **{item['name']}**: {item['progress']}% complete\n"
            if item['behind_schedule']:
                briefing += f"  ⚠️ Behind schedule by {item['days_behind']} days\n"
        
        briefing += "\n"
        
        # Personal goals check
        briefing += "💪 **PERSONAL GOALS:**\n"
        goals_status = self.check_personal_goals()
        for goal in goals_status:
            briefing += f"• **{goal['name']}**: Day {goal['current_day']} of {goal['total_days']}\n"
            if goal['missed_yesterday']:
                briefing += f"  ❌ Missed yesterday - don't break the streak!\n"
            if goal['due_today']:
                briefing += f"  ✅ Due today: {goal['requirement']}\n"
        
        briefing += "\n"
        
        # Intelligent recommendations
        briefing += "🧠 **INTELLIGENT RECOMMENDATIONS:**\n"
        recommendations = self.generate_recommendations()
        for rec in recommendations:
            briefing += f"• {rec}\n"
        
        briefing += "\n"
        
        # Critical alerts
        alerts = self.get_critical_alerts()
        if alerts:
            briefing += "🚨 **CRITICAL ALERTS:**\n"
            for alert in alerts:
                briefing += f"• {alert.message}\n"
            briefing += "\n"
        
        briefing += "🚀 **Ready to dominate today? Let's make it count!**\n"
        
        return briefing
    
    def get_todays_priorities(self) -> List[Dict]:
        """Get today's top priorities"""
        now = datetime.now()
        today = now.date()
        
        priorities = []
        
        # Check deadlines for today
        for deadline in self.deadlines.values():
            if deadline.due_date.date() == today:
                priorities.append({
                    'name': deadline.name,
                    'category': deadline.category,
                    'priority': deadline.priority,
                    'time': deadline.due_date.strftime('%I:%M %p'),
                    'status': f"{deadline.progress*100:.0f}% complete"
                })
        
        # Check daily goals
        for goal in self.goals.values():
            if goal.daily_requirement:
                priorities.append({
                    'name': goal.name,
                    'category': goal.category,
                    'priority': 0.8,
                    'time': None,
                    'status': goal.daily_requirement
                })
        
        # Sort by priority
        priorities.sort(key=lambda x: x['priority'], reverse=True)
        
        return priorities[:5]  # Top 5
    
    def get_urgent_deadlines(self, days_threshold: int = 7) -> List[Deadline]:
        """Get deadlines that are approaching"""
        now = datetime.now()
        urgent = []
        
        for deadline in self.deadlines.values():
            if deadline.status in ['pending', 'in_progress']:
                days_left = (deadline.due_date - now).days
                if 0 <= days_left <= days_threshold:
                    urgent.append(deadline)
        
        # Sort by urgency (days left, then priority)
        urgent.sort(key=lambda x: ((x.due_date - now).days, -x.priority))
        
        return urgent
    
    def get_progress_summary(self) -> List[Dict]:
        """Get progress summary for active items"""
        now = datetime.now()
        progress_items = []
        
        for deadline in self.deadlines.values():
            if deadline.status == 'in_progress':
                # Calculate if behind schedule
                total_time = deadline.due_date - datetime(2024, 12, 1)  # Assume started Dec 1
                elapsed_time = now - datetime(2024, 12, 1)
                expected_progress = elapsed_time.total_seconds() / total_time.total_seconds()
                
                behind_schedule = deadline.progress < expected_progress
                days_behind = max(0, int((expected_progress - deadline.progress) * total_time.days))
                
                progress_items.append({
                    'name': deadline.name,
                    'progress': int(deadline.progress * 100),
                    'behind_schedule': behind_schedule,
                    'days_behind': days_behind
                })
        
        return progress_items
    
    def check_personal_goals(self) -> List[Dict]:
        """Check status of personal goals"""
        now = datetime.now()
        yesterday = now - timedelta(days=1)
        
        goals_status = []
        
        for goal in self.goals.values():
            if goal.daily_requirement:
                # Calculate current day
                if goal.name == '75 Hard Challenge':
                    start_date = datetime(2024, 12, 7)  # Estimated start
                    current_day = (now - start_date).days + 1
                    total_days = 75
                    
                    missed_yesterday = goal.last_completed and goal.last_completed.date() < yesterday.date()
                    
                    goals_status.append({
                        'name': goal.name,
                        'current_day': current_day,
                        'total_days': total_days,
                        'missed_yesterday': missed_yesterday,
                        'due_today': True,
                        'requirement': goal.daily_requirement
                    })
        
        return goals_status
    
    def generate_recommendations(self) -> List[str]:
        """Generate intelligent recommendations based on current status"""
        recommendations = []
        
        # Academic recommendations
        db_deadline = self.deadlines.get('database_exam')
        if db_deadline and db_deadline.due_date.date() == datetime.now().date():
            recommendations.append("🎓 Database exam today - review normalization one more time before 2pm")
        
        # Coding recommendations  
        remi_deadline = self.deadlines.get('remi_whiteboard')
        if remi_deadline and remi_deadline.progress < 0.7:
            days_left = (remi_deadline.due_date - datetime.now()).days
            recommendations.append(f"💻 Remi whiteboard feature 60% done, {days_left} days left - focus 3 hours today")
        
        # Business recommendations
        salary_deadline = self.deadlines.get('abayomi_salary')
        if salary_deadline and salary_deadline.status == 'pending':
            recommendations.append("💰 Abayomi's salary due in 2 days - prepare payment process")
        
        # Personal recommendations
        goal_75 = self.goals.get('75_hard')
        if goal_75:
            now = datetime.now()
            if not goal_75.last_completed or goal_75.last_completed.date() < now.date():
                recommendations.append("💪 You haven't worked out yet today (75 Hard Day 24) - schedule it now")
        
        # Time management recommendations
        recommendations.append("⏰ Block 2 hours for focused work on highest priority project")
        recommendations.append("📝 Review and update project progress before end of day")
        
        return recommendations[:5]  # Top 5
    
    def get_critical_alerts(self) -> List[Alert]:
        """Get critical alerts that need immediate attention"""
        critical_alerts = []
        now = datetime.now()
        
        # Check for overdue items
        for deadline in self.deadlines.values():
            if deadline.due_date < now and deadline.status != 'completed':
                critical_alerts.append(Alert(
                    message=f"{deadline.name} is overdue!",
                    priority='critical',
                    category=deadline.category,
                    action_required=True,
                    deadline=deadline.due_date,
                    created=now
                ))
        
        # Check for goals at risk
        for goal in self.goals.values():
            if goal.daily_requirement:
                if goal.last_completed and (now - goal.last_completed).days > 1:
                    critical_alerts.append(Alert(
                        message=f"{goal.name} streak at risk - complete today's requirement",
                        priority='high',
                        category=goal.category,
                        action_required=True,
                        deadline=None,
                        created=now
                    ))
        
        return critical_alerts
    
    def update_deadline(self, deadline_key: str, progress: float = None, status: str = None) -> None:
        """Update deadline progress or status"""
        if deadline_key in self.deadlines:
            if progress is not None:
                self.deadlines[deadline_key].progress = progress
            if status is not None:
                self.deadlines[deadline_key].status = status
            
            self.save_deadlines()
            logger.info(f"Updated deadline {deadline_key}: progress={progress}, status={status}")
    
    def complete_daily_goal(self, goal_key: str) -> None:
        """Mark daily goal as completed for today"""
        if goal_key in self.goals:
            now = datetime.now()
            self.goals[goal_key].last_completed = now
            self.goals[goal_key].streak += 1
            
            self.save_goals()
            logger.info(f"Completed daily goal {goal_key}, streak now {self.goals[goal_key].streak}")
    
    def add_deadline(self, name: str, due_date: datetime, category: str, priority: float, 
                     description: str = "", estimated_hours: float = 1.0) -> str:
        """Add new deadline"""
        deadline_key = name.lower().replace(' ', '_')
        
        self.deadlines[deadline_key] = Deadline(
            name=name,
            due_date=due_date,
            category=category,
            priority=priority,
            description=description,
            status='pending',
            estimated_hours=estimated_hours,
            progress=0.0,
            reminders=[]
        )
        
        self.save_deadlines()
        return deadline_key
    
    def get_weekly_overview(self) -> str:
        """Generate weekly overview"""
        now = datetime.now()
        week_start = now - timedelta(days=now.weekday())
        week_end = week_start + timedelta(days=6)
        
        overview = f"📅 **WEEK OVERVIEW** ({week_start.strftime('%B %d')} - {week_end.strftime('%B %d')})\n\n"
        
        # This week's deadlines
        week_deadlines = []
        for deadline in self.deadlines.values():
            if week_start <= deadline.due_date <= week_end:
                week_deadlines.append(deadline)
        
        if week_deadlines:
            overview += "📋 **This Week's Deadlines:**\n"
            for deadline in sorted(week_deadlines, key=lambda x: x.due_date):
                overview += f"• **{deadline.name}**: {deadline.due_date.strftime('%A %I:%M %p')}\n"
            overview += "\n"
        
        # Goals progress
        overview += "🎯 **Goals Progress:**\n"
        for goal in self.goals.values():
            overview += f"• **{goal.name}**: {goal.progress*100:.0f}% complete\n"
        
        return overview
    
    def save_deadlines(self) -> None:
        """Save deadlines to disk"""
        try:
            serializable = {}
            for key, deadline in self.deadlines.items():
                serializable[key] = {
                    'name': deadline.name,
                    'due_date': deadline.due_date.isoformat(),
                    'category': deadline.category,
                    'priority': deadline.priority,
                    'description': deadline.description,
                    'status': deadline.status,
                    'estimated_hours': deadline.estimated_hours,
                    'progress': deadline.progress,
                    'reminders': [r.isoformat() for r in deadline.reminders]
                }
            
            with open(self.deadlines_file, 'w') as f:
                json.dump(serializable, f, indent=2)
                
        except Exception as e:
            logger.error(f"Failed to save deadlines: {e}")
    
    def load_deadlines(self) -> Dict[str, Deadline]:
        """Load deadlines from disk"""
        try:
            if self.deadlines_file.exists():
                with open(self.deadlines_file, 'r') as f:
                    data = json.load(f)
                
                deadlines = {}
                for key, deadline_data in data.items():
                    deadlines[key] = Deadline(
                        name=deadline_data['name'],
                        due_date=datetime.fromisoformat(deadline_data['due_date']),
                        category=deadline_data['category'],
                        priority=deadline_data['priority'],
                        description=deadline_data['description'],
                        status=deadline_data['status'],
                        estimated_hours=deadline_data['estimated_hours'],
                        progress=deadline_data['progress'],
                        reminders=[datetime.fromisoformat(r) for r in deadline_data['reminders']]
                    )
                
                return deadlines
                
        except Exception as e:
            logger.warning(f"Failed to load deadlines: {e}")
        
        return {}
    
    def save_goals(self) -> None:
        """Save goals to disk"""
        try:
            serializable = {}
            for key, goal in self.goals.items():
                serializable[key] = {
                    'name': goal.name,
                    'category': goal.category,
                    'target_date': goal.target_date.isoformat(),
                    'description': goal.description,
                    'progress': goal.progress,
                    'milestones': goal.milestones,
                    'daily_requirement': goal.daily_requirement,
                    'streak': goal.streak,
                    'last_completed': goal.last_completed.isoformat() if goal.last_completed else None
                }
            
            with open(self.goals_file, 'w') as f:
                json.dump(serializable, f, indent=2)
                
        except Exception as e:
            logger.error(f"Failed to save goals: {e}")
    
    def load_goals(self) -> Dict[str, Goal]:
        """Load goals from disk"""
        try:
            if self.goals_file.exists():
                with open(self.goals_file, 'r') as f:
                    data = json.load(f)
                
                goals = {}
                for key, goal_data in data.items():
                    goals[key] = Goal(
                        name=goal_data['name'],
                        category=goal_data['category'],
                        target_date=datetime.fromisoformat(goal_data['target_date']),
                        description=goal_data['description'],
                        progress=goal_data['progress'],
                        milestones=goal_data['milestones'],
                        daily_requirement=goal_data['daily_requirement'],
                        streak=goal_data['streak'],
                        last_completed=datetime.fromisoformat(goal_data['last_completed']) if goal_data['last_completed'] else None
                    )
                
                return goals
                
        except Exception as e:
            logger.warning(f"Failed to load goals: {e}")
        
        return {}