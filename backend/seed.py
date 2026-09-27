import hashlib
import os
import sys
from pathlib import Path

# Ensure repo root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.app.settings import get_settings
from backend.app.db import get_engine, init_db, get_session_factory
from backend.app.models import Document, Annotation, Relation, Label, RelationType
from backend.app.services.ingest import process_document


def seed_database() -> int:
    """Ingest sample.pdf and seed initial annotations and relations."""
    settings = get_settings()
    engine = get_engine()
    init_db(engine_override=engine)
    session_factory = get_session_factory(engine)

    sample_pdf = Path("sample/sample.pdf")
    if not sample_pdf.exists():
        print(f"Error: {sample_pdf} not found.")
        sys.exit(1)

    with open(sample_pdf, "rb") as f:
        pdf_bytes = f.read()

    file_hash = hashlib.sha256(pdf_bytes).hexdigest()
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    saved_path = upload_dir / f"{file_hash}.pdf"
    with open(saved_path, "wb") as f:
        f.write(pdf_bytes)

    with session_factory() as session:
        # Check if already seeded
        doc = session.query(Document).filter(Document.file_hash == file_hash).first()
        if not doc:
            doc = Document(
                filename="sample.pdf",
                file_hash=file_hash,
                status="processing",
            )
            session.add(doc)
            session.commit()
            session.refresh(doc)
        doc_id = doc.id

    print(f"Processing document {doc_id} ({saved_path})...")
    process_document(None, doc_id, str(saved_path))

    with session_factory() as session:
        doc = session.query(Document).filter(Document.id == doc_id).first()
        clean_text = doc.clean_text or ""

        # Remove previous seed annotations if re-running
        session.query(Annotation).filter(Annotation.document_id == doc_id).delete()
        session.commit()

        # Seed annotations matching exact phrases in sample text
        quotes_to_seed = [
            ("Can machines think?", "Problem", "Turing's fundamental philosophical question", 150.0, 100.0),
            ("The definitions might be framed so as to reflect so far as possible the normal use of the words, but this attitude is dangerous.", "Claim", "Critique of conventional definitions", 150.0, 220.0),
            ("Digital computers can simulate any discrete state machine.", "Evidence", "Discrete state equivalence property", 450.0, 100.0),
            ("They can all be done with one digital computer, suitably programmed for each case.", "Solution", "Sufficiency of a single universal computer", 450.0, 220.0),
        ]

        created_anns = []
        for quote, label, note, x, y in quotes_to_seed:
            idx = clean_text.find(quote)
            if idx != -1:
                start = idx
                end = idx + len(quote)
                ann = Annotation(
                    document_id=doc_id,
                    start=start,
                    end=end,
                    quote=quote,
                    label=label,
                    note=note,
                    x=x,
                    y=y,
                    version=1,
                )
                session.add(ann)
                created_anns.append(ann)

        session.commit()
        for a in created_anns:
            session.refresh(a)

        # Seed relationships
        if len(created_anns) >= 4:
            # 1. Ann 0 (Problem) -> Ann 3 (Solution) relates_to
            r1 = Relation(
                document_id=doc_id,
                source_id=created_anns[0].id,
                target_id=created_anns[3].id,
                type="relates_to",
                status="confirmed",
                reason="The universal machine provides an answer to the thinking machine question",
                version=1,
            )
            # 2. Ann 2 (Evidence) -> Ann 3 (Solution) supports
            r2 = Relation(
                document_id=doc_id,
                source_id=created_anns[2].id,
                target_id=created_anns[3].id,
                type="supports",
                status="confirmed",
                reason="Simulation equivalence supports universal applicability",
                version=1,
            )
            session.add_all([r1, r2])
            session.commit()

        print(f"Successfully seeded database for Document ID {doc_id} with {len(created_anns)} annotations and 2 relations!")
        return doc_id


if __name__ == "__main__":
    seed_database()
