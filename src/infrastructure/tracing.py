"""
OpenTelemetry tracing configuration.

Centralizes tracing setup for the application.
"""
import os
import logging
import sys

logger = logging.getLogger(__name__)


def setup_tracing() -> bool:
    """
    Configure OpenTelemetry tracing with Azure Monitor.
    
    Returns:
        True if tracing was configured successfully, False otherwise.
    """
    try:
        # Avoid re-initializing tracing on reruns
        if os.environ.get("OTEL_CONFIGURED") == "true":
            logger.info("Tracing already configured; skipping re-initialization")
            return True

        from azure.ai.projects import AIProjectClient
        from azure.identity import (
            AzureCliCredential,
            VisualStudioCodeCredential,
            EnvironmentCredential,
            ManagedIdentityCredential,
            ChainedTokenCredential,
        )
        from azure.monitor.opentelemetry import configure_azure_monitor
        from azure.core.settings import settings
        
        # Get connection string from Foundry project
        project_endpoint = os.getenv("AZURE_AI_PROJECT_ENDPOINT")
        if not project_endpoint:
            logger.warning("AZURE_AI_PROJECT_ENDPOINT not set - tracing disabled")
            return False
        
        credential = ChainedTokenCredential(
            EnvironmentCredential(),
            AzureCliCredential(),
            VisualStudioCodeCredential(),
            ManagedIdentityCredential(),
        )
        
        project_client = AIProjectClient(
            credential=credential,
            endpoint=project_endpoint,
        )
        
        # Get Application Insights connection string
        connection_string = project_client.telemetry.get_application_insights_connection_string()
        
        if not connection_string:
            logger.warning("No Application Insights connected - tracing disabled")
            return False
        
        logger.info("Retrieved Application Insights connection string")
        
        # Enable content recording for debugging
        os.environ["AZURE_TRACING_GEN_AI_CONTENT_RECORDING_ENABLED"] = "true"
        os.environ["OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT"] = "true"
        
        # Enable Azure SDK tracing
        settings.tracing_implementation = "opentelemetry"
        
        # Configure Azure Monitor
        configure_azure_monitor(
            connection_string=connection_string,
            enable_live_metrics=True
        )
        
        # Instrument OpenAI SDK
        try:
            from opentelemetry.instrumentation.openai_v2 import OpenAIInstrumentor
            if os.environ.get("OTEL_OPENAI_INSTRUMENTED") != "true":
                OpenAIInstrumentor().instrument()
                os.environ["OTEL_OPENAI_INSTRUMENTED"] = "true"
                logger.info("OpenAI SDK instrumentation enabled")
        except ImportError as e:
            logger.warning(
                f"opentelemetry-instrumentation-openai-v2 not installed: {e}"
            )
        
        os.environ["OTEL_CONFIGURED"] = "true"
        logger.info("OpenTelemetry tracing configured successfully")
        return True
        
    except ImportError as e:
        logger.warning(f"Tracing packages not installed: {e}")
        return False
    except Exception as e:
        logger.warning(f"Failed to configure tracing: {e}")
        return False
