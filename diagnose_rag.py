#!/usr/bin/env python3
"""Diagnostic script for EduAI Africa RAG Pipeline."""
import asyncio
import sys
from uuid import UUID
from sqlalchemy import select, func
import numpy as np

# Make sure app is in path
import os
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from app.database import AsyncSessionLocal, engine
from app.models.document import Document
from app.models.document_chunk import DocumentChunk


async def diagnose():
    print("=" * 70)
    print("🎓 EduAI Africa RAG Pipeline - Outil de Diagnostic")
    print("=" * 70)
    
    async with AsyncSessionLocal() as db:
        # Get total documents
        doc_stmt = select(Document)
        doc_res = await db.execute(doc_stmt)
        docs = doc_res.scalars().all()
        
        print(f"\n📂 Nombre total de documents enregistrés : {len(docs)}")
        
        if not docs:
            print("❌ Aucun document trouvé en base de données.")
            return
            
        print("\n🔍 Analyse par document :")
        print("-" * 70)
        
        unindexed_count = 0
        corrupt_count = 0
        indexed_count = 0
        
        for doc in docs:
            # Get chunks count for this document
            chunk_stmt = select(DocumentChunk).where(DocumentChunk.document_id == doc.id)
            chunk_res = await db.execute(chunk_stmt)
            chunks = chunk_res.scalars().all()
            
            chunk_len = len(chunks)
            print(f"\n📄 Document : {doc.filename}")
            print(f"   ID       : {doc.id}")
            print(f"   Statut   : {doc.status.value}")
            print(f"   Chunks   : {chunk_len}")
            
            if chunk_len == 0:
                print("   ⚠️ Statut d'indexation : NON INDEXÉ (0 chunk)")
                unindexed_count += 1
                continue
                
            # Inspect first chunk's embedding
            first_chunk = chunks[0]
            emb = first_chunk.embedding
            
            if emb is None:
                print("   ❌ Statut d'indexation : CORROMPU (embeddings manquants)")
                corrupt_count += 1
                continue
                
            dim = len(emb)
            print(f"   Dimension: {dim}")
            
            # Check for zero vectors
            zero_count = 0
            nan_count = 0
            for chunk in chunks:
                c_emb = chunk.embedding
                if c_emb is None:
                    zero_count += 1
                    continue
                # NumPy array checks
                c_emb_arr = np.array(c_emb)
                if np.all(c_emb_arr == 0.0):
                    zero_count += 1
                if np.any(np.isnan(c_emb_arr)):
                    nan_count += 1
                    
            print(f"   Vecteurs nuls (Zeros) : {zero_count} / {chunk_len}")
            if nan_count > 0:
                print(f"   Vecteurs avec NaN     : {nan_count} / {chunk_len}")
                
            if zero_count > 0 or nan_count > 0:
                print("   ❌ Statut d'indexation : CORROMPU (certains embeddings sont nuls ou invalides)")
                corrupt_count += 1
            else:
                print("   ✅ Statut d'indexation : INDEXÉ (embeddings valides)")
                indexed_count += 1
                
        print("\n" + "=" * 70)
        print("📊 RÉSUMÉ GLOBAL")
        print("=" * 70)
        print(f"   ✅ Documents indexés (Valides) : {indexed_count}")
        print(f"   ❌ Documents corrompus (Zéro/NaN) : {corrupt_count}")
        print(f"   ⚠️ Documents non indexés : {unindexed_count}")
        print("=" * 70)


if __name__ == "__main__":
    # Run async function
    asyncio.run(diagnose())
