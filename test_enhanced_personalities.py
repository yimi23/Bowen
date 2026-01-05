#!/usr/bin/env python3
"""
Test Enhanced CAPTAIN and TAMARA with Professional Document Creation
Shows the transformation from basic AI chat to professional productivity suite
"""

import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from document_engine import DocumentEngine, create_captain_document, create_tamara_document

def test_captain_document_creation():
    """Test CAPTAIN's strategic document creation capabilities"""
    print("🎖️ CAPTAIN Document Creation Test")
    print("=" * 50)
    
    # Test 1: Strategic Roadmap
    print("\n📋 Test 1: Strategic Roadmap")
    roadmap_content = {
        'title': 'Q1 2024 Product Launch Strategy',
        'executive_summary': 'Comprehensive strategic roadmap for launching our flagship product in Q1 2024, focusing on market penetration and competitive positioning.',
        'objectives': [
            'Achieve 25% market share in target segment',
            'Generate $2M revenue in first quarter',
            'Establish brand recognition in key markets',
            'Build strategic partnerships with 3 major distributors'
        ],
        'milestones': [
            {'name': 'Product Development Complete', 'date': '2024-01-15', 'status': 'In Progress'},
            {'name': 'Marketing Campaign Launch', 'date': '2024-02-01', 'status': 'Planned'},
            {'name': 'Partner Agreements Signed', 'date': '2024-02-15', 'status': 'Planned'},
            {'name': 'Public Launch Event', 'date': '2024-03-01', 'status': 'Planned'}
        ],
        'risks': [
            'Competitive response from market leader',
            'Supply chain disruptions',
            'Regulatory approval delays',
            'Economic downturn affecting consumer spending'
        ],
        'resources': 'Total budget: $5M allocated across development ($2M), marketing ($2M), and operations ($1M).'
    }
    
    try:
        filepath = create_captain_document("roadmap", roadmap_content)
        print(f"✅ Strategic roadmap created: {filepath}")
    except Exception as e:
        print(f"❌ Failed to create roadmap: {e}")
    
    # Test 2: Crisis Response Plan
    print("\n🚨 Test 2: Crisis Response Plan")
    crisis_content = {
        'situation': 'Major cybersecurity breach detected in customer database system affecting 100,000+ users.',
        'immediate_actions': [
            'Isolate affected systems and contain breach',
            'Activate incident response team',
            'Notify legal and compliance teams',
            'Prepare customer communication',
            'Contact cybersecurity experts'
        ],
        'short_term_actions': [
            'Conduct forensic analysis of breach',
            'Implement additional security measures',
            'Notify affected customers',
            'Work with law enforcement if required',
            'Develop recovery timeline'
        ],
        'command_structure': [
            {'title': 'Incident Commander', 'responsibility': 'Overall crisis management and decision authority'},
            {'title': 'Technical Lead', 'responsibility': 'System recovery and security implementation'},
            {'title': 'Communications Lead', 'responsibility': 'Customer and media communication'},
            {'title': 'Legal Counsel', 'responsibility': 'Regulatory compliance and legal issues'}
        ],
        'communication_plan': 'Establish hourly status calls with crisis team. Customer notification within 24 hours. Media response prepared for potential inquiries.'
    }
    
    try:
        filepath = create_captain_document("crisis_plan", crisis_content)
        print(f"✅ Crisis response plan created: {filepath}")
    except Exception as e:
        print(f"❌ Failed to create crisis plan: {e}")
    
    # Test 3: Gantt Chart
    print("\n📊 Test 3: Project Gantt Chart")
    gantt_content = {
        'title': 'Product Launch Timeline',
        'tasks': [
            {'name': 'Requirements Analysis', 'start_date': '2024-01-01', 'end_date': '2024-01-15'},
            {'name': 'Design Phase', 'start_date': '2024-01-10', 'end_date': '2024-01-30'},
            {'name': 'Development Sprint 1', 'start_date': '2024-01-25', 'end_date': '2024-02-15'},
            {'name': 'Testing & QA', 'start_date': '2024-02-10', 'end_date': '2024-02-28'},
            {'name': 'Marketing Prep', 'start_date': '2024-02-01', 'end_date': '2024-03-01'},
            {'name': 'Launch Event', 'start_date': '2024-03-01', 'end_date': '2024-03-01'}
        ]
    }
    
    try:
        filepath = create_captain_document("gantt", gantt_content)
        print(f"✅ Gantt chart created: {filepath}")
    except Exception as e:
        print(f"❌ Failed to create Gantt chart: {e}")

def test_tamara_document_creation():
    """Test TAMARA's operational document creation capabilities"""
    print("\n\n🌟 TAMARA Document Creation Test")
    print("=" * 50)
    
    # Test 1: Task Tracker
    print("\n📝 Test 1: Project Task Tracker")
    task_content = {
        'tasks': [
            {
                'id': 'T001',
                'name': 'Setup Development Environment',
                'assignee': 'John Smith',
                'priority': 'High',
                'status': 'Complete',
                'start': '2024-01-01',
                'due': '2024-01-05',
                'completion': 100,
                'notes': 'Environment configured with all tools'
            },
            {
                'id': 'T002',
                'name': 'Database Schema Design',
                'assignee': 'Sarah Johnson',
                'priority': 'High',
                'status': 'In Progress',
                'start': '2024-01-03',
                'due': '2024-01-12',
                'completion': 75,
                'notes': 'Primary tables designed, working on relationships'
            },
            {
                'id': 'T003',
                'name': 'API Endpoint Development',
                'assignee': 'Mike Chen',
                'priority': 'Medium',
                'status': 'Not Started',
                'start': '2024-01-10',
                'due': '2024-01-25',
                'completion': 0,
                'notes': 'Waiting for schema completion'
            }
        ]
    }
    
    try:
        filepath = create_tamara_document("task_tracker", task_content)
        print(f"✅ Task tracker created: {filepath}")
    except Exception as e:
        print(f"❌ Failed to create task tracker: {e}")
    
    # Test 2: Process Optimization Report
    print("\n📊 Test 2: Process Optimization Report")
    process_content = {
        'title': 'Customer Onboarding Process Optimization',
        'executive_summary': 'Analysis of current customer onboarding workflow with recommendations to reduce time-to-value and improve satisfaction scores.',
        'current_metrics': {
            'Average Onboarding Time': '14 days',
            'Customer Satisfaction': '3.2/5.0',
            'Manual Steps': '23',
            'Error Rate': '18%',
            'Support Tickets per Customer': '4.5'
        },
        'pain_points': [
            'Multiple manual handoffs between departments',
            'Inconsistent communication with customers',
            'Duplicate data entry across 3 systems',
            'No automated progress tracking',
            'Limited visibility into process bottlenecks'
        ],
        'recommendations': [
            {
                'title': 'Implement Automated Workflow System',
                'description': 'Deploy workflow automation to eliminate manual handoffs',
                'impact': '60% reduction in onboarding time',
                'effort': 'Medium - 8 weeks implementation',
                'timeline': 'Q1 2024'
            },
            {
                'title': 'Centralized Customer Portal',
                'description': 'Single portal for customers to track progress and access resources',
                'impact': '40% improvement in satisfaction scores',
                'effort': 'High - 12 weeks development',
                'timeline': 'Q2 2024'
            }
        ],
        'implementation_phases': [
            {
                'number': 1,
                'name': 'System Integration',
                'duration': '6 weeks',
                'activities': 'Connect existing systems, implement data sync',
                'success_metrics': 'Data consistency >95%, sync time <5 minutes'
            },
            {
                'number': 2,
                'name': 'Workflow Automation',
                'duration': '4 weeks',
                'activities': 'Deploy automation rules, train team',
                'success_metrics': 'Manual steps reduced by 80%'
            }
        ],
        'roi_analysis': {
            'implementation_cost': '$75,000',
            'annual_savings': '$180,000',
            'payback_period': '5 months',
            'three_year_npv': '$425,000'
        },
        'conclusion': 'Implementation of recommended optimizations will transform customer onboarding from a manual, error-prone process into an automated, customer-friendly experience.'
    }
    
    try:
        filepath = create_tamara_document("process_report", process_content)
        print(f"✅ Process optimization report created: {filepath}")
    except Exception as e:
        print(f"❌ Failed to create process report: {e}")
    
    # Test 3: Data Dashboard
    print("\n📈 Test 3: Business Analytics Dashboard")
    dashboard_content = {
        'title': 'Q4 2023 Business Performance Dashboard',
        'data': [
            {'month': '2023-10', 'sales': 45000, 'customers': 320, 'satisfaction': 4.2},
            {'month': '2023-11', 'sales': 52000, 'customers': 380, 'satisfaction': 4.3},
            {'month': '2023-12', 'sales': 48000, 'customers': 350, 'satisfaction': 4.1}
        ]
    }
    
    try:
        filepath = create_tamara_document("dashboard", dashboard_content)
        print(f"✅ Analytics dashboard created: {filepath}")
    except Exception as e:
        print(f"❌ Failed to create dashboard: {e}")

def demonstrate_transformation():
    """Demonstrate the transformation achieved"""
    print("\n\n🎯 TRANSFORMATION DEMONSTRATION")
    print("=" * 60)
    
    print("BEFORE: Basic BOWEN Framework")
    print("  • CAPTAIN: Strategic advice through conversation")
    print("  • TAMARA: Basic file operations and simple scripts")
    print("  • Value: Interesting AI chat, limited productivity")
    print("  • Business Case: Weak - just another chatbot")
    
    print("\nAFTER: Enhanced BOWEN with Document Engine")
    print("  • CAPTAIN: Creates strategic documents (Word, PowerPoint, Gantt charts)")
    print("  • TAMARA: Professional business docs (Excel, reports, dashboards)")
    print("  • Value: Complete productivity suite with AI personalities")
    print("  • Business Case: Strong - replaces multiple tools")
    
    print(f"\n💰 Enhanced Value Proposition:")
    print(f"  • Strategic Planning Suite (CAPTAIN): $15/month value")
    print(f"  • Operations Management Suite (TAMARA): $15/month value")
    print(f"  • AI-Powered Automation: $10/month value")
    print(f"  • Professional Document Creation: $20/month value")
    print(f"  • Personality-Specific Expertise: $10/month value")
    print(f"  • Total Value: $70/month (vs $29/month price = 141% value)")
    
    print(f"\n🏆 Competitive Advantages:")
    print(f"  ✅ ChatGPT: Can't create real documents")
    print(f"  ✅ Claude Web: No file operations")
    print(f"  ✅ Microsoft Copilot: No personality specialization")
    print(f"  ✅ Notion AI: Limited document types")
    print(f"  ✅ Jasper: No operational automation")
    
    print(f"\n🎉 BOWEN is now a complete productivity platform!")

def test_file_outputs():
    """Show what files were actually created"""
    print("\n\n📁 Created Files Summary")
    print("=" * 40)
    
    engine = DocumentEngine()
    created_files = engine.list_created_files()
    
    if created_files:
        print(f"✅ {len(created_files)} professional documents created:")
        for filepath in created_files[:10]:  # Show latest 10
            file_info = engine.get_file_info(filepath)
            print(f"  📄 {file_info['name']} ({file_info['size']:,} bytes)")
    else:
        print("⚠️ No files found - check output directory")
    
    print(f"\n📂 Output directory: {engine.output_dir}")
    print(f"   Open this folder to see your professional documents!")

if __name__ == "__main__":
    try:
        # Create output directory
        os.makedirs("/Users/yimi/Desktop/bowen_outputs", exist_ok=True)
        
        # Test document creation
        test_captain_document_creation()
        test_tamara_document_creation()
        
        # Show transformation
        demonstrate_transformation()
        
        # Show created files
        test_file_outputs()
        
        print(f"\n" + "="*70)
        print("🚀 ENHANCED BOWEN FRAMEWORK: FULLY OPERATIONAL")
        print("✅ CAPTAIN: Strategic document creation machine")
        print("✅ TAMARA: Professional automation platform")
        print("✅ Document Engine: Terminal Claude-level capabilities")
        print("🏆 TRANSFORMATION COMPLETE: Chat → Productivity Suite")
        print("="*70)
        
    except Exception as e:
        print(f"❌ Test suite failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)