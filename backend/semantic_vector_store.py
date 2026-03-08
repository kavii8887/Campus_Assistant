"""
semantic_vector_store.py
Vector DB wrapper used by DepartmentRouter.
"""
from typing import List, Dict, Any, Optional


class SemanticVectorStore:
    """
    Vector database for UNIT CONTENT.
    Wrapper to match runtime expectations.
    """

    def __init__(self, collection_name: str, embedding_dim: int, persist_path: str = "./vector_db"):
        from qdrant_client import QdrantClient
        from qdrant_client.models import Distance, VectorParams

        self.collection_name = collection_name
        self.embedding_dim = embedding_dim
        self.client = QdrantClient(path=persist_path)
        self._initialize_collection()

    def _initialize_collection(self):
        from qdrant_client.models import Distance, VectorParams

        collections = self.client.get_collections().collections

        if any(c.name == self.collection_name for c in collections):
            print(f"✓ Vector collection '{self.collection_name}' exists")
        else:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=self.embedding_dim,
                    distance=Distance.COSINE,
                    on_disk=True
                ),
            )
            print(f"✓ Created vector collection '{self.collection_name}'")

    def ingest_chunks(self, chunks_with_metadata, embeddings):
        """Insert chunks into Qdrant."""
        from qdrant_client.models import PointStruct
        import uuid

        points = []

        for idx, ((text, metadata), embedding) in enumerate(zip(chunks_with_metadata, embeddings)):
            payload = dict(metadata)
            payload["text"] = text

            point_id = str(uuid.uuid4())

            points.append(
                PointStruct(
                    id=point_id,
                    vector=embedding,
                    payload=payload
                )
            )

        if points:
            self.client.upsert(
                collection_name=self.collection_name,
                points=points
            )

            print(f"  ✓ Stored {len(points)} chunks into '{self.collection_name}'")

    def retrieve_by_course(
        self,
        course_code: str,
        unit_number: Optional[str] = None,
        top_k: int = 50
    ) -> List[Dict[str, Any]]:
        from qdrant_client.models import Filter, FieldCondition, MatchValue

        must_conditions = [
            FieldCondition(key="course_code", match=MatchValue(value=course_code))
        ]

        if unit_number:
            must_conditions.append(
                FieldCondition(key="unit_number", match=MatchValue(value=unit_number))
            )

        search_filter = Filter(must=must_conditions)

        results, _ = self.client.scroll(
            collection_name=self.collection_name,
            scroll_filter=search_filter,
            limit=top_k,
            with_payload=True,
            with_vectors=False
        )

        results = sorted(results, key=lambda x: x.payload.get('chunk_index', 0))

        return [
            {
                'text': r.payload['text'],
                'metadata': {k: v for k, v in r.payload.items() if k != 'text'}
            }
            for r in results
        ]

    def search(self, query_embedding: List[float], top_k: int = 10) -> List[Dict[str, Any]]:
        results = self.client.query_points(
            collection_name=self.collection_name,
            query=query_embedding,
            limit=top_k,
            with_payload=True
        ).points

        return [
            {
                'text': r.payload['text'],
                'metadata': {k: v for k, v in r.payload.items() if k != 'text'},
                'score': r.score
            }
            for r in results
        ]