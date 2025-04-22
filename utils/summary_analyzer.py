import os
from typing import List, Dict, Any, Optional
from datetime import datetime
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field, field_validator
from langchain_anthropic import ChatAnthropic
from dotenv import load_dotenv
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from collections import Counter

load_dotenv()

# Pydantic models for structured output
class TopicSentiment(BaseModel):
    """A topic discussed in the conversation with its sentiment."""
    topic: str = Field(description="The topic or specific subject discussed")
    sentiment: str = Field(description="The sentiment toward this topic: positive, negative, neutral, or mixed")
    importance: int = Field(description="Importance score from 1-5, with 5 being most important")
    
    @field_validator('sentiment')
    def validate_sentiment(cls, v):
        valid_sentiments = ['positive', 'negative', 'neutral', 'mixed']
        if v.lower() not in valid_sentiments:
            raise ValueError(f"Sentiment must be one of: {', '.join(valid_sentiments)}")
        return v.lower()
    
    @field_validator('importance')
    def validate_importance(cls, v):
        if not 1 <= v <= 5:
            raise ValueError("Importance must be between 1 and 5")
        return v

class ConversationInsight(BaseModel):
    """Extracted insights from a conversation summary."""
    main_intent: str = Field(description="The main goal or intention of the user in this conversation")
    topics: List[TopicSentiment] = Field(description="List of topics discussed with sentiment and importance")
    user_satisfaction: int = Field(description="Estimated user satisfaction score (1-5)")
    key_questions: List[str] = Field(description="Key questions asked by the user")
    action_items: List[str] = Field(description="Action items or next steps identified")
    conversation_type: str = Field(description="Type of conversation: inquiry, support, feedback, complaint, etc.")
    
    @field_validator('user_satisfaction')
    def validate_satisfaction(cls, v):
        if not 1 <= v <= 5:
            raise ValueError("User satisfaction must be between 1 and 5")
        return v

class SummaryAnalyzer:
    def __init__(self, model_name="gpt-4o"):
        """Initialize the analyzer with the specified model."""
        self.llm = None
        
        # Configure the language model based on what's available
        if os.getenv("OPENAI_API_KEY") and model_name.startswith("gpt"):
            self.llm = ChatOpenAI(model=model_name, temperature=0)
        elif os.getenv("ANTHROPIC_API_KEY") and model_name.startswith("claude"):
            self.llm = ChatAnthropic(model=model_name, temperature=0)
        else:
            # Fallback to OpenAI
            self.llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0)
            
        # Create the prompt template
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", "You are an expert conversation analyst tasked with extracting structured insights from conversation summaries. Analyze the provided summary and extract key information in a structured format."),
            ("user", """
            Analyze the following conversation summary and extract structured insights.
            
            CONVERSATION SUMMARY:
            {summary}
            
            INSTRUCTIONS:
            - Identify the main intent or goal of the user
            - Extract key topics discussed with their sentiment and importance (1-5)
            - Estimate overall user satisfaction (1-5)
            - Identify key questions asked by the user
            - Extract any action items or next steps
            - Categorize the conversation type
            """)
        ])
        
        # Create structured LLM with Pydantic model
        self.structured_llm = self.llm.with_structured_output(ConversationInsight)
        
        # Create the chain
        self.chain = self.prompt | self.structured_llm
    
    def analyze_summary(self, summary: str) -> ConversationInsight:
        """Analyze a single conversation summary and return structured insights."""
        if not summary or len(summary.strip()) < 10:
            raise ValueError("Summary is too short or empty")
        
        try:
            result = self.chain.invoke({"summary": summary})
            return result
        except Exception as e:
            print(f"Error analyzing summary: {e}")
            raise
    
    def analyze_multiple_summaries(self, summaries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Analyze multiple summaries and return results with metadata.
        
        Args:
            summaries: List of dictionaries containing summary text and metadata
                       Each dict should have at least 'summary_id', 'summary', 'user_id', 'session_id'
        
        Returns:
            List of dictionaries with original metadata and added analysis results
        """
        results = []
        
        for summary_item in summaries:
            try:
                # Extract the summary text
                summary_text = summary_item.get('summary', '')
                
                if not summary_text or len(summary_text.strip()) < 10:
                    print(f"Skipping summary {summary_item.get('summary_id', 'unknown')}: too short or empty")
                    continue
                
                # Analyze the summary
                analysis = self.analyze_summary(summary_text)
                
                # Combine original metadata with analysis
                result = {
                    **summary_item,
                    'analysis': analysis.model_dump()  # Use model_dump() instead of dict() in Pydantic v2
                }
                
                results.append(result)
            except Exception as e:
                print(f"Error analyzing summary {summary_item.get('summary_id', 'unknown')}: {e}")
        
        return results

    @staticmethod
    def generate_topic_heatmap(analyses: List[Dict[str, Any]]):
        """
        Generate a heatmap of topics by sentiment and importance.
        
        Args:
            analyses: List of dictionaries with analysis results
        
        Returns:
            Plotly figure
        """
        # Collect all topics with their sentiment and importance
        topic_data = []
        
        for analysis in analyses:
            if 'analysis' in analysis and 'topics' in analysis['analysis']:
                for topic in analysis['analysis']['topics']:
                    topic_data.append({
                        'topic': topic.get('topic', 'Unknown'),
                        'sentiment': topic.get('sentiment', 'neutral'),
                        'importance': topic.get('importance', 3)
                    })
        
        if not topic_data:
            # Return empty figure with message
            fig = go.Figure()
            fig.add_annotation(
                text="No topic data available",
                xref="paper", yref="paper",
                x=0.5, y=0.5, showarrow=False
            )
            return fig
        
        # Convert to DataFrame
        df = pd.DataFrame(topic_data)
        
        # Count occurrences of each topic-sentiment combination
        topic_counts = df.groupby(['topic', 'sentiment', 'importance']).size().reset_index(name='count')
        
        # Create a pivot table for the heatmap
        pivot_df = topic_counts.pivot_table(
            index='topic', 
            columns='sentiment', 
            values='count', 
            aggfunc='sum',
            fill_value=0
        )
        
        # Create heatmap
        fig = px.imshow(
            pivot_df,
            labels=dict(x="Sentiment", y="Topic", color="Count"),
            x=pivot_df.columns,
            y=pivot_df.index,
            aspect="auto",
            color_continuous_scale='Viridis'
        )
        
        fig.update_layout(
            title="Topic Sentiment Heatmap",
            xaxis_title="Sentiment",
            yaxis_title="Topic",
            height=600
        )
        
        return fig
    
    @staticmethod
    def generate_satisfaction_chart(analyses: List[Dict[str, Any]]):
        """
        Generate a chart showing user satisfaction distribution.
        
        Args:
            analyses: List of dictionaries with analysis results
        
        Returns:
            Plotly figure
        """
        # Extract satisfaction scores
        satisfaction_scores = []
        
        for analysis in analyses:
            if 'analysis' in analysis and 'user_satisfaction' in analysis['analysis']:
                satisfaction_scores.append(analysis['analysis']['user_satisfaction'])
        
        if not satisfaction_scores:
            # Return empty figure with message
            fig = go.Figure()
            fig.add_annotation(
                text="No satisfaction data available",
                xref="paper", yref="paper",
                x=0.5, y=0.5, showarrow=False
            )
            return fig
        
        # Count occurrences of each score
        score_counts = Counter(satisfaction_scores)
        scores = list(range(1, 6))  # Scores from 1 to 5
        counts = [score_counts.get(score, 0) for score in scores]
        
        # Create bar chart
        fig = go.Figure(data=[
            go.Bar(
                x=scores,
                y=counts,
                marker_color=['#FF4136', '#FF851B', '#FFDC00', '#2ECC40', '#0074D9'],  # Red to blue
                text=counts,
                textposition='auto'
            )
        ])
        
        fig.update_layout(
            title="User Satisfaction Distribution",
            xaxis_title="Satisfaction Score",
            yaxis_title="Number of Conversations",
            xaxis=dict(
                tickmode='array',
                tickvals=scores,
                ticktext=['Very Low (1)', 'Low (2)', 'Neutral (3)', 'High (4)', 'Very High (5)']
            ),
            height=400
        )
        
        return fig
    
    @staticmethod
    def generate_conversation_types_chart(analyses: List[Dict[str, Any]]):
        """
        Generate a pie chart showing conversation type distribution.
        
        Args:
            analyses: List of dictionaries with analysis results
        
        Returns:
            Plotly figure
        """
        # Extract conversation types
        conversation_types = []
        
        for analysis in analyses:
            if 'analysis' in analysis and 'conversation_type' in analysis['analysis']:
                conversation_types.append(analysis['analysis']['conversation_type'])
        
        if not conversation_types:
            # Return empty figure with message
            fig = go.Figure()
            fig.add_annotation(
                text="No conversation type data available",
                xref="paper", yref="paper",
                x=0.5, y=0.5, showarrow=False
            )
            return fig
        
        # Count occurrences of each type
        type_counts = Counter(conversation_types)
        
        # Create pie chart
        fig = go.Figure(data=[
            go.Pie(
                labels=list(type_counts.keys()),
                values=list(type_counts.values()),
                hole=0.4,
                textinfo='label+percent',
                insidetextorientation='radial'
            )
        ])
        
        fig.update_layout(
            title="Conversation Types Distribution",
            height=400
        )
        
        return fig
    
    @staticmethod
    def generate_top_questions_table(analyses: List[Dict[str, Any]], top_n: int = 10):
        """
        Generate a table of top questions asked by users.
        
        Args:
            analyses: List of dictionaries with analysis results
            top_n: Number of top questions to include
        
        Returns:
            Plotly figure
        """
        # Extract all questions
        all_questions = []
        
        for analysis in analyses:
            if 'analysis' in analysis and 'key_questions' in analysis['analysis']:
                all_questions.extend(analysis['analysis']['key_questions'])
        
        if not all_questions:
            # Return empty figure with message
            fig = go.Figure()
            fig.add_annotation(
                text="No questions data available",
                xref="paper", yref="paper",
                x=0.5, y=0.5, showarrow=False
            )
            return fig
        
        # Count occurrences of each question
        question_counts = Counter(all_questions)
        
        # Get top N questions
        top_questions = question_counts.most_common(top_n)
        
        # Create table
        fig = go.Figure(data=[
            go.Table(
                header=dict(
                    values=['Question', 'Frequency'],
                    fill_color='#0074D9',
                    align='left',
                    font=dict(color='white', size=14)
                ),
                cells=dict(
                    values=[
                        [q for q, _ in top_questions],
                        [c for _, c in top_questions]
                    ],
                    fill_color='lavender',
                    align='left',
                    font=dict(size=12)
                )
            )
        ])
        
        fig.update_layout(
            title="Top User Questions",
            height=400 + (len(top_questions) * 25)  # Adjust height based on number of entries
        )
        
        return fig