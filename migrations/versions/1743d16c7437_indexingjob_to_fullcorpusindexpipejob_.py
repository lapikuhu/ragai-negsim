"""IndexingJob to FullCorpusIndexPipeJob naming convention fix

Revision ID: 1743d16c7437
Revises: b4d5e6f7a8b9
Create Date: 2026-07-27 21:31:07.630987
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '1743d16c7437'
down_revision = 'b4d5e6f7a8b9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.rename_table('indexingjob', 'fullcorpusindexpipejob')
    op.rename_table('indexingjobwarning', 'fullcorpusindexpipejobwarning')

    op.alter_column(
        'fullcorpusindexpipejobwarning',
        'indexing_job_id',
        new_column_name='full_corpus_index_pipe_job_id',
        existing_type=sa.Integer(),
        existing_nullable=False,
    )
    op.alter_column(
        'documentchunk',
        'indexing_job_id',
        new_column_name='full_corpus_index_pipe_job_id',
        existing_type=sa.Integer(),
        existing_nullable=True,
    )

    op.execute(
        'ALTER TABLE fullcorpusindexpipejob '
        'RENAME CONSTRAINT indexingjob_pkey TO fullcorpusindexpipejob_pkey'
    )
    op.execute(
        'ALTER TABLE fullcorpusindexpipejob '
        'RENAME CONSTRAINT indexingjob_candidate_corpus_index_id_fkey '
        'TO fullcorpusindexpipejob_candidate_corpus_index_id_fkey'
    )
    op.execute(
        'ALTER TABLE fullcorpusindexpipejob '
        'RENAME CONSTRAINT indexingjob_chunking_profile_id_fkey '
        'TO fullcorpusindexpipejob_chunking_profile_id_fkey'
    )
    op.execute(
        'ALTER TABLE fullcorpusindexpipejob '
        'RENAME CONSTRAINT indexingjob_corpus_id_fkey '
        'TO fullcorpusindexpipejob_corpus_id_fkey'
    )
    op.execute(
        'ALTER TABLE fullcorpusindexpipejob '
        'RENAME CONSTRAINT indexingjob_current_raw_document_id_fkey '
        'TO fullcorpusindexpipejob_current_raw_document_id_fkey'
    )
    op.execute(
        'ALTER TABLE fullcorpusindexpipejob '
        'RENAME CONSTRAINT indexingjob_replaced_corpus_index_id_fkey '
        'TO fullcorpusindexpipejob_replaced_corpus_index_id_fkey'
    )
    op.execute(
        'ALTER TABLE fullcorpusindexpipejob '
        'RENAME CONSTRAINT indexingjob_vector_store_id_fkey '
        'TO fullcorpusindexpipejob_vector_store_id_fkey'
    )
    op.execute(
        'ALTER TABLE fullcorpusindexpipejobwarning '
        'RENAME CONSTRAINT indexingjobwarning_pkey TO fullcorpusindexpipejobwarning_pkey'
    )
    op.execute(
        'ALTER TABLE fullcorpusindexpipejobwarning '
        'RENAME CONSTRAINT indexingjobwarning_indexing_job_id_fkey '
        'TO fullcorpusindexpipejobwarning_full_corpus_index_pipe_job_id_fkey'
    )
    op.execute(
        'ALTER TABLE fullcorpusindexpipejobwarning '
        'RENAME CONSTRAINT indexingjobwarning_raw_document_id_fkey '
        'TO fullcorpusindexpipejobwarning_raw_document_id_fkey'
    )
    op.execute(
        'ALTER TABLE documentchunk '
        'RENAME CONSTRAINT documentchunk_indexing_job_id_fkey '
        'TO documentchunk_full_corpus_index_pipe_job_id_fkey'
    )

    op.execute(
        'ALTER INDEX ix_indexingjob_corpus_id RENAME TO ix_fullcorpusindexpipejob_corpus_id'
    )
    op.execute('ALTER INDEX ix_indexingjob_stage RENAME TO ix_fullcorpusindexpipejob_stage')
    op.execute('ALTER INDEX ix_indexingjob_status RENAME TO ix_fullcorpusindexpipejob_status')
    op.execute(
        'ALTER INDEX ix_indexingjobwarning_indexing_job_id '
        'RENAME TO ix_fullcorpusindexpipejobwarning_full_corpus_index_pipe_job_id'
    )

    op.execute('ALTER SEQUENCE IF EXISTS indexingjob_id_seq RENAME TO fullcorpusindexpipejob_id_seq')
    op.execute(
        'ALTER SEQUENCE IF EXISTS indexingjobwarning_id_seq '
        'RENAME TO fullcorpusindexpipejobwarning_id_seq'
    )


def downgrade() -> None:
    op.execute(
        'ALTER SEQUENCE IF EXISTS fullcorpusindexpipejob_id_seq RENAME TO indexingjob_id_seq'
    )
    op.execute(
        'ALTER SEQUENCE IF EXISTS fullcorpusindexpipejobwarning_id_seq '
        'RENAME TO indexingjobwarning_id_seq'
    )

    op.execute(
        'ALTER INDEX ix_fullcorpusindexpipejob_corpus_id RENAME TO ix_indexingjob_corpus_id'
    )
    op.execute('ALTER INDEX ix_fullcorpusindexpipejob_stage RENAME TO ix_indexingjob_stage')
    op.execute('ALTER INDEX ix_fullcorpusindexpipejob_status RENAME TO ix_indexingjob_status')
    op.execute(
        'ALTER INDEX ix_fullcorpusindexpipejobwarning_full_corpus_index_pipe_job_id '
        'RENAME TO ix_indexingjobwarning_indexing_job_id'
    )

    op.execute(
        'ALTER TABLE documentchunk '
        'RENAME CONSTRAINT documentchunk_full_corpus_index_pipe_job_id_fkey '
        'TO documentchunk_indexing_job_id_fkey'
    )
    op.execute(
        'ALTER TABLE fullcorpusindexpipejobwarning '
        'RENAME CONSTRAINT fullcorpusindexpipejobwarning_pkey TO indexingjobwarning_pkey'
    )
    op.execute(
        'ALTER TABLE fullcorpusindexpipejobwarning '
        'RENAME CONSTRAINT fullcorpusindexpipejobwarning_full_corpus_index_pipe_job_id_fkey '
        'TO indexingjobwarning_indexing_job_id_fkey'
    )
    op.execute(
        'ALTER TABLE fullcorpusindexpipejobwarning '
        'RENAME CONSTRAINT fullcorpusindexpipejobwarning_raw_document_id_fkey '
        'TO indexingjobwarning_raw_document_id_fkey'
    )
    op.execute(
        'ALTER TABLE fullcorpusindexpipejob '
        'RENAME CONSTRAINT fullcorpusindexpipejob_pkey TO indexingjob_pkey'
    )
    op.execute(
        'ALTER TABLE fullcorpusindexpipejob '
        'RENAME CONSTRAINT fullcorpusindexpipejob_candidate_corpus_index_id_fkey '
        'TO indexingjob_candidate_corpus_index_id_fkey'
    )
    op.execute(
        'ALTER TABLE fullcorpusindexpipejob '
        'RENAME CONSTRAINT fullcorpusindexpipejob_chunking_profile_id_fkey '
        'TO indexingjob_chunking_profile_id_fkey'
    )
    op.execute(
        'ALTER TABLE fullcorpusindexpipejob '
        'RENAME CONSTRAINT fullcorpusindexpipejob_corpus_id_fkey '
        'TO indexingjob_corpus_id_fkey'
    )
    op.execute(
        'ALTER TABLE fullcorpusindexpipejob '
        'RENAME CONSTRAINT fullcorpusindexpipejob_current_raw_document_id_fkey '
        'TO indexingjob_current_raw_document_id_fkey'
    )
    op.execute(
        'ALTER TABLE fullcorpusindexpipejob '
        'RENAME CONSTRAINT fullcorpusindexpipejob_replaced_corpus_index_id_fkey '
        'TO indexingjob_replaced_corpus_index_id_fkey'
    )
    op.execute(
        'ALTER TABLE fullcorpusindexpipejob '
        'RENAME CONSTRAINT fullcorpusindexpipejob_vector_store_id_fkey '
        'TO indexingjob_vector_store_id_fkey'
    )

    op.alter_column(
        'documentchunk',
        'full_corpus_index_pipe_job_id',
        new_column_name='indexing_job_id',
        existing_type=sa.Integer(),
        existing_nullable=True,
    )
    op.alter_column(
        'fullcorpusindexpipejobwarning',
        'full_corpus_index_pipe_job_id',
        new_column_name='indexing_job_id',
        existing_type=sa.Integer(),
        existing_nullable=False,
    )

    op.rename_table('fullcorpusindexpipejobwarning', 'indexingjobwarning')
    op.rename_table('fullcorpusindexpipejob', 'indexingjob')
