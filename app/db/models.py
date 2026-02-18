import uuid
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import Column, String, JSON, ForeignKey, UniqueConstraint, Text, DateTime, func, Integer
import datetime

Base = declarative_base() # lauches a fresh drawing board

#regulations table
class Regulation(Base):
    """
    OSFI B-10 
    """
    __tablename__ = 'regulations'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    section = Column(String, nullable=False)
    text_content = Column(Text, nullable=False)

    #for audit
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    #relationship with compliance
    compliance_results = relationship("ComplianceResult", back_populates="regulation")

    __table_args__=(
        UniqueConstraint("name", "section", name = "uq_regulations_name_section"),
    )

#internal policy
class InternalPolicy(Base):
    __tablename__ = 'internal_policies'

    id= Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    version = Column(String, nullable=False)
    text_content = Column(Text, nullable=False)


    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    #relationship
    compliance_results = relationship("ComplianceResult", back_populates="policy")

    __table_args__=(
        UniqueConstraint("name", "version", name="uq_policy_name_version"),
    )

class DocumentChunk(Base):
    """
    The atomic unit of retrieval - stores paragraphs drawn from regulations & internal polices to be used as chunks for vec embedding.
    Serves as the backup & sources of truth for the managed vector store.
    """
    __tablename__ = "document_chunks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id = Column(UUID(as_uuid=True), nullable=False) #can be either regualation & policy
    source_type = Column(String, nullable=False)
    chunk_index = Column(Integer, nullable=False)
    text_content = Column(Text, nullable=False)
    chunk_metadata= Column(JSON, nullable=True)
    embedding_id = Column(String, nullable=True) # id in QDRANT

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    #adding unique constraint to ensure accurate chunk ordering & no duplication of chunks

    __table_args__ = (
        UniqueConstraint("source_id", "source_type", "chunk_index", name="uq_document_chunk_order")
        ,)



class ComplianceResult(Base):
    __tablename__ = "compliance_results"

    id= Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    regulation_id = Column(UUID(as_uuid=True), ForeignKey('regulations.id'))
    policy_id = Column(UUID(as_uuid=True), ForeignKey('internal_policies.id'))

    #AI Analyst

    status = Column(String, nullable=False) # Pass, Fail, ambigious
    confidence_score = Column(String, nullable=False) # high, medium, low
    reasoning = Column(Text, nullable=False)

    #Audit trail for llm

    model_name = Column(String, nullable=False)
    agent_metadata = Column(JSON) # prompt, tokens etc.

    #db audit
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    #relationship
    regulation = relationship("Regulation", back_populates="compliance_results")
    policy = relationship("InternalPolicy", back_populates="compliance_results")



 






