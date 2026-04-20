"""
Analyst Agent module for SentinelFlow.

Extracts structured task information from meeting transcripts using LangChain
with Google Generative AI (Gemini 2.5 Flash) and generates vector embeddings for semantic search.
"""

import os
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser


class ExtractedTask(BaseModel):
    """
    Structured representation of a task extracted from a transcript.
    
    Attributes:
        description: The action item description
        owner: Name of the person responsible; defaults to "Unassigned" if not mentioned
        deadline: Optional deadline in ISO format (YYYY-MM-DD)
    """

    description: str = Field(
        description="Clear, concise description of the action item"
    )
    owner: str = Field(
        default="Unassigned", description="Name of the person responsible"
    )
    deadline: Optional[str] = Field(
        default=None, description="Deadline date in YYYY-MM-DD format if mentioned"
    )
    embedding: Optional[List[float]] = None


class TaskList(BaseModel):
    """
    Container class for structured task extraction output.
    
    Wraps a list of ExtractedTask objects to ensure compatibility with
    structured output in Python 3.13+ where typing.List is not a concrete class.
    """

    tasks: List[ExtractedTask] = Field(
        default_factory=list, description="List of extracted tasks from the transcript"
    )


class AnalystAgent:
    """
    Analyst agent for extracting and processing tasks from meeting transcripts.
    
    Uses Google Generative AI's Gemini 2.5 Flash model for task extraction and
    embedding-005 for generating vector embeddings.
    """

    def __init__(self):
        """Initialize the Analyst agent with LLM and embedding models.
        
        Uses Application Default Credentials (ADC) for authentication.
        Credentials are automatically loaded from the environment.
        """
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-3.1-flash-lite-preview",
            temperature=0.7,
            max_tokens=2048,
        )
        self.embeddings_model = GoogleGenerativeAIEmbeddings(model="models/text-embedding-005",project="bright-antonym-492507-k4")
        self._setup_extraction_chain()

    def _setup_extraction_chain(self):
        """Set up the LangChain extraction pipeline."""
        self.extraction_prompt = PromptTemplate(
            input_variables=["transcript"],
            template="""You are an AI assistant specialized in extracting action items from meeting transcripts.

Please analyze the following meeting transcript and extract ALL action items, tasks, and deliverables mentioned.

For each action item, provide:
1. A clear, detailed description of what needs to be done
2. The person responsible (if explicitly mentioned; otherwise leave null)
3. Any mentioned deadline or due date in ISO format (if mentioned; otherwise leave null)

Format your response as a JSON array of objects with keys: description, owner, deadline

Meeting Transcript:
{transcript}

Extract all action items and return them as a JSON array. If no action items are found, return an empty array [].

JSON Array of Extracted Tasks:""",
        )

        self.structured_llm = self.llm.with_structured_output(TaskList)

    def extract_tasks(self, transcript: str) -> List[ExtractedTask]:
        """
        Extract structured tasks from a meeting transcript.
        
        Args:
            transcript: Raw meeting transcript text
            
        Returns:
            List of ExtractedTask objects
        """
        if not transcript or not transcript.strip():
            return []

        try:
            prompt_value = self.extraction_prompt.format(transcript=transcript)
            result = self.structured_llm.invoke(prompt_value)

            # Extract tasks from the TaskList container
            tasks = result.tasks if hasattr(result, 'tasks') else []

            return tasks
        except Exception as e:
            print(f"Error extracting tasks: {e}")
            return []

    def generate_embedding(self, text: str) -> List[float]:
        """
        Generate a vector embedding for the given text using Google Generative AI.
        
        Args:
            text: Text to embed
            
        Returns:
            768-dimensional embedding vector
        """
        if not text or not text.strip():
            return [0.0] * 768

        try:
            embedding = self.embeddings_model.embed_query(text)
            return embedding
        except Exception as e:
            print(f"Error generating embedding for text '{text[:100]}...': {e}")
            # Return zero vector on error
            return [0.0] * 768

    def process_transcript(self, transcript: str):
        """
        End-to-end processing: extract tasks and generate embeddings.
        
        Args:
            transcript: Raw meeting transcript
            
        Returns:
            List of ExtractedTask objects with embeddings
        """
        tasks = self.extract_tasks(transcript)

        for task in tasks:
            task.embedding = self.generate_embedding(task.description)

        return tasks


# Global analyst instance
_analyst = None


def get_analyst() -> AnalystAgent:
    """Get or create the global Analyst agent instance."""
    global _analyst
    if _analyst is None:
        _analyst = AnalystAgent()
    return _analyst


def extract_tasks_from_transcript(transcript: str) -> List[ExtractedTask]:
    """
    Extract tasks from a meeting transcript.
    
    Args:
        transcript: Meeting transcript text
        
    Returns:
        List of extracted tasks with embeddings
    """
    analyst = get_analyst()
    return analyst.process_transcript(transcript)
