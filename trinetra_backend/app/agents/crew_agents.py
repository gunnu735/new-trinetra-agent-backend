import json
import structlog
from crewai import Agent, Task, Crew, Process
from langchain_groq import ChatGroq
from app.core.config import settings

logger = structlog.get_logger()

def get_llm():
    return ChatGroq(
        api_key=settings.GROQ_API_KEY,
        model="llama3-70b-8192",
        temperature=0.3,
    )

def run_agent_pipeline(extracted_data: dict, recipient_email: str) -> dict:
    try:
        llm = get_llm()

        pdf_analyzer = Agent(
            role="PDF Document Analyzer",
            goal="Extract and structure key information from PDF document content",
            backstory="You are an expert document analyst who extracts structured information from documents.",
            llm=llm,
            verbose=True,
            allow_delegation=False,
            max_iter=3,
        )

        email_composer = Agent(
            role="Professional Email Composer",
            goal="Compose a professional email based on document analysis",
            backstory="You are an expert email writer who crafts clear and professional emails.",
            llm=llm,
            verbose=True,
            allow_delegation=False,
            max_iter=3,
        )

        email_delivery_agent = Agent(
            role="Email Delivery Coordinator",
            goal="Prepare final email metadata for delivery",
            backstory="You are responsible for finalizing email details before sending.",
            llm=llm,
            verbose=True,
            allow_delegation=False,
            max_iter=2,
        )

        full_text = extracted_data.get("full_text", "")[:3000]
        metadata = extracted_data.get("metadata", {})

        analyze_task = Task(
            description=f"""
            Analyze the following document content and extract structured information.
            Return a JSON with: title, summary, key_entities, main_topics, document_type.

            Document Metadata: {json.dumps(metadata)}
            Document Content: {full_text}

            Return ONLY valid JSON, nothing else.
            """,
            expected_output="A JSON object with title, summary, key_entities, main_topics, document_type",
            agent=pdf_analyzer,
        )

        compose_task = Task(
            description=f"""
            Based on the document analysis, compose a professional email to {recipient_email}.
            The email should summarize the document and highlight key points.
            Return a JSON with: subject, body, priority.

            Return ONLY valid JSON, nothing else.
            """,
            expected_output="A JSON object with subject, body, priority fields",
            agent=email_composer,
            context=[analyze_task],
        )

        delivery_task = Task(
            description="""
            Review the composed email and prepare final delivery metadata.
            Return a JSON with: subject, body, ready_to_send (true/false), notes.

            Return ONLY valid JSON, nothing else.
            """,
            expected_output="A JSON object with subject, body, ready_to_send, notes",
            agent=email_delivery_agent,
            context=[compose_task],
        )

        crew = Crew(
            agents=[pdf_analyzer, email_composer, email_delivery_agent],
            tasks=[analyze_task, compose_task, delivery_task],
            process=Process.sequential,
            verbose=True,
        )

        result = crew.kickoff()
        result_str = str(result)

        try:
            start = result_str.find('{')
            end = result_str.rfind('}') + 1
            if start >= 0 and end > start:
                final_output = json.loads(result_str[start:end])
            else:
                final_output = {"subject": "Document Summary", "body": result_str, "ready_to_send": True}
        except Exception:
            final_output = {"subject": "Document Summary", "body": result_str, "ready_to_send": True}

        logger.info("crew_pipeline_completed")
        return {
            "analysis": analyze_task.output.raw if analyze_task.output else "",
            "email_subject": final_output.get("subject", "Document Summary"),
            "email_body": final_output.get("body", result_str),
        }

    except Exception as e:
        logger.error("crew_pipeline_failed", error=str(e))
        raise Exception(f"Agent pipeline failed: {str(e)}")
