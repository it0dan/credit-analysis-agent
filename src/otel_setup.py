"""
otel_setup.py
Configuração do OpenTelemetry SDK com OTLP exporter e suporte a propagação W3C.
"""

import os
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from opentelemetry.propagate import set_global_textmap

import sys

# 1. Definindo atributos de recurso do serviço
service_name = "credit-analysis-mas"
service_version = os.environ.get("SERVICE_VERSION", "1.0.0")

resource = Resource.create({
    "service.name": service_name,
    "service.version": service_version
})

# 2. Inicializando TracerProvider
provider = TracerProvider(resource=resource)

# 3. Configurando OTLP Exporter apenas se OTEL_EXPORTER_OTLP_ENDPOINT estiver definido
otlp_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
if otlp_endpoint:
    try:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
        processor = BatchSpanProcessor(exporter)
        provider.add_span_processor(processor)
        print(f"  [otel] OTLP Exporter habilitado apontando para {otlp_endpoint}.", file=sys.stderr)
    except Exception as e:
        print(f"  [otel] Falha ao inicializar OTLP Exporter: {e}", file=sys.stderr)
else:
    print("  [otel] OTLP Exporter desabilitado (OTEL_EXPORTER_OTLP_ENDPOINT não definido).", file=sys.stderr)

trace.set_tracer_provider(provider)

# 4. Configurando propagação padrão W3C (traceparent + tracestate)
set_global_textmap(TraceContextTextMapPropagator())

def get_tracer(name: str):
    """
    Retorna o Tracer correspondente ao nome do módulo.
    """
    return trace.get_tracer(name)
