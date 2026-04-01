# -*- coding: utf-8 -*-
from .core import GraphRAGLite
try:
    from .neo4j_store import Neo4jStore
    __all__ = ["GraphRAGLite", "Neo4jStore"]
except ImportError:
    __all__ = ["GraphRAGLite"]

__version__ = "0.1.2"
