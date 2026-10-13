"""Optional diagnostics. Research history and artifacts remain local and authoritative."""

from contextlib import contextmanager
from uuid import uuid4

from .config import settings


class Trace:
    def __init__(self, run_id, inputs, enabled=True, name="process_episode"):
        self.id = str(uuid4())
        self.root = None
        self.status = "disabled"
        self.url = None
        if not (enabled and settings.langsmith_tracing and settings.langsmith_api_key):
            return
        try:
            from langsmith import Client, RunTree

            self.root = RunTree(
                id=self.id,
                name=name,
                run_type="chain",
                project_name=settings.langsmith_project,
                client=Client(api_key=settings.langsmith_api_key),
                inputs=dict(inputs, research_run_id=run_id),
            )
            self.root.post()
            self.status = "pending"
        except Exception:
            self.root = None
            self.status = "error"

    @contextmanager
    def span(self, name, inputs, run_type="tool"):
        span = None
        output = {}
        if self.root:
            try:
                span = self.root.create_child(
                    name=name, run_type=run_type, inputs=inputs
                )
                span.post()
            except Exception:
                self.status = "error"
        try:
            yield output
        except Exception as exc:
            if span:
                try:
                    span.end(error=str(exc))
                    span.patch()
                except Exception:
                    self.status = "error"
            raise
        else:
            if span:
                try:
                    span.end(outputs=output)
                    span.patch()
                except Exception:
                    self.status = "error"

    def finish(self, result=None, error=None):
        if self.root:
            try:
                self.root.end(outputs=result, error=error or "")
                self.root.patch()
                self.url = self.root.get_url()
                self.status = "submitted"
            except Exception:
                self.status = "error"
