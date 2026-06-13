export type paths = {
    "/chunking-profiles/": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Chunking Profiles
         * @description List chunking profiles endpoint with optional filters and pagination.
         *         Args:
         *             session: The database session.
         *             _admin: The admin dependency.
         *             page: The pagination parameters.
         *             strategy: Optional filter to list profiles by chunking strategy.
         *             name_contains: Optional filter to list profiles whose names
         *                 contain a substring.
         *             has_references: Optional filter to list profiles that are
         *                 referenced by corpus indices.
         *         Returns:
         *             A list of ChunkingProfileReadWithIds objects matching the
         *             filters and pagination.
         */
        get: operations["list_chunking_profiles_chunking_profiles__get"];
        put?: never;
        /**
         * Create Chunking Profile
         * @description Create a new chunking profile endpoint.
         *         Args:
         *             profile_data: The data to create the chunking profile with.
         *             session: The database session.
         *             _admin: The admin dependency.
         *         Returns:
         *             A ChunkingProfileReadWithIds object containing the created
         *             chunking profile data and associated corpus index IDs.
         *         Raises:
         *             HTTPException: If the chunking profile cannot be created due to
         *             validation errors or other constraints, with a 409 status code and
         *             error detail.
         */
        post: operations["create_chunking_profile_chunking_profiles__post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/chunking-profiles/{profile_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Chunking Profile
         * @description Get a chunking profile by ID endpoint.
         *         Args:
         *             profile: The admin chunking profile dependency.
         *             session: The database session.
         *         Returns:
         *             A ChunkingProfileReadWithIds object containing the chunking
         *             profile data and associated corpus index IDs.
         */
        get: operations["get_chunking_profile_chunking_profiles__profile_id__get"];
        put?: never;
        post?: never;
        /**
         * Delete Chunking Profile
         * @description Delete a chunking profile endpoint.
         *         Args:
         *             profile: The admin chunking profile dependency for the profile
         *                 to delete.
         *             session: The database session.
         *         Returns:
         *             None
         *         Raises:
         *             HTTPException: If the chunking profile cannot be deleted due to
         *             existing references or other constraints, with a 409 status code
         *             and error detail.
         */
        delete: operations["delete_chunking_profile_chunking_profiles__profile_id__delete"];
        options?: never;
        head?: never;
        /**
         * Update Chunking Profile
         * @description Update a chunking profile endpoint.
         *         Args:
         *             profile_data: The data to update the chunking profile with.
         *             profile: The admin chunking profile dependency.
         *             session: The database session.
         *         Returns:
         *             A ChunkingProfileReadWithIds object containing the updated
         *             chunking profile data and associated corpus index IDs.
         *         Raises:
         *             HTTPException: If the chunking profile cannot be updated due to
         *             validation errors or other constraints, with a 409 status code and
         *             error detail.
         */
        patch: operations["update_chunking_profile_chunking_profiles__profile_id__patch"];
        trace?: never;
    };
    "/chunking-profiles/{profile_id}/copy": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Copy Chunking Profile
         * @description Copy a chunking profile endpoint.
         *         Args:
         *             copy_data: The data for the new chunking profile to create from
         *                 the source profile.
         *             source_profile: The admin chunking profile dependency for the
         *                 source profile to copy.
         *             session: The database session.
         *         Returns:
         *             A ChunkingProfileReadWithIds object containing the new copied
         *             chunking profile data and associated corpus index IDs.
         *         Raises:
         *             HTTPException: If the chunking profile cannot be copied due to
         *             validation errors or other constraints, with a 409 status code and
         *             error detail.
         */
        post: operations["copy_chunking_profile_chunking_profiles__profile_id__copy_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/chunking-profiles/definitions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Chunker Definitions
         * @description List chunker definitions endpoint.
         *         Args:
         *             _admin: The admin dependency.
         *         Returns:
         *             A list of ChunkerDefinitionRead objects containing the chunker
         *             definitions.
         */
        get: operations["list_chunker_definitions_chunking_profiles_definitions_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/corpora/": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Corpora
         * @description Endpoint to list all corpora.
         *     Args:
         *         session: The database session to use for the operation.
         *         skip: The number of records to skip for pagination.
         *         limit: The maximum number of records to return.
         *         created_by_user_id: Optional filter to return corpora created by a
         *             specific user.
         *         raw_document_id: Optional filter to return corpora associated with a
         *             specific raw document.
         *         has_indices: Optional filter to return corpora that have indices.
         *     Returns:
         *         A list of CorpusRead instances representing all corpora.
         */
        get: operations["list_corpora_corpora__get"];
        put?: never;
        /**
         * Create Corpus
         * @description Endpoint to create a new corpus.
         *     Args:
         *         corpus_data: The data for the corpus to be created.
         *         session: The database session to use for the operation.
         *         current_user: The user creating the corpus.
         *     Returns:
         *         The created CorpusRead instance.
         */
        post: operations["create_corpus_corpora__post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/corpora/{corpus_id}/chunking-profiles/{profile_id}/chunk": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Chunk Corpus
         * @description Endpoint to chunk already parsed raw documents linked to a corpus.
         *     Args:
         *         corpus: The writable corpus to chunk.
         *         chunking_profile: The chunking profile to associate with created
         *             chunks.
         *         session: The database session to use for persistence.
         *         options: Query options controlling chunking behavior.
         *     Returns:
         *         A summary of created or previewed chunks per raw document.
         */
        post: operations["chunk_corpus_corpora__corpus_id__chunking_profiles__profile_id__chunk_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/corpora/{corpus_id}/chunking-profiles/{profile_id}/ingest": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Ingest Corpus
         * @description Endpoint to ingest and parse all raw documents linked to a corpus.
         *     Args:
         *         corpus: The writable corpus to ingest.
         *         chunking_profile: The chunking profile to associate with created
         *             chunks.
         *         session: The database session to use for persistence.
         *         options: Query options controlling parsing and chunking.
         *     Returns:
         *         A summary of created chunks per raw document.
         */
        post: operations["ingest_corpus_corpora__corpus_id__chunking_profiles__profile_id__ingest_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/corpora/{corpus_id}/chunking-profiles/{profile_id}/vector-stores/{vector_store_id}/embed": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Embed Corpus
         * @description Build a vector index for corpus chunks using a selected embedding model
         *     and vector store.
         *     Args:
         *         corpus: The writable corpus to embed.
         *         chunking_profile: The chunking profile associated with the chunks
         *             to embed.
         *         vector_store: The vector store record specifying where to store
         *             embeddings.
         *         build_in: The parameters for building the corpus embeddings.
         *         session: The database session to use for any necessary queries or
         *             updates.
         *         _admin: The current admin user performing the operation
         *             (for authorization).
         *     Returns:
         *         A summary of the embedding build process, including counts of processed
         *         chunks and any errors.
         */
        post: operations["embed_corpus_corpora__corpus_id__chunking_profiles__profile_id__vector_stores__vector_store_id__embed_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/corpora/{corpus_id}/chunking-profiles/{profile_id}/vector-stores/{vector_store_id}/embed-jobs": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Queue Embed Corpus Job
         * @description Queue a background vector index build for corpus chunks using a selected
         *     embedding model and vector store.
         *     Args:
         *         corpus: The writable corpus to embed.
         *         chunking_profile: The chunking profile associated with the chunks
         *             to embed.
         *         vector_store: The vector store record specifying where to store
         *             embeddings.
         *         build_in: The parameters for building the corpus embeddings.
         *         session: The database session to use for any necessary queries or
         *             updates.
         *         background_tasks: The background tasks manager to schedule the
         *             embedding build.
         *         _admin: The current admin user performing the operation
         *             (for authorization).
         *     Returns:
         *         The queued embedding build job details.
         *     Raises:
         *         HTTPException: If the embedding build request is invalid or cannot
         *         be queued.
         */
        post: operations["queue_embed_corpus_job_corpora__corpus_id__chunking_profiles__profile_id__vector_stores__vector_store_id__embed_jobs_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/corpus-indices/": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Corpus Indices
         * @description List corpus indices endpoint.
         *     Args:
         *         session (AsyncSession): the database session
         *         _admin (CorpusIndexAdminDep): the admin dependency
         *         page (Page): the pagination parameters
         *         corpus_id (int | None): filter by corpus ID
         *         vector_store_id (int | None): filter by vector store ID
         *         chunking_profile_id (int | None): filter by chunking profile ID
         *         status (str | None): filter by status
         *         has_indexed_chunks (bool | None): filter by whether the index
         *             has indexed chunks
         *     Returns:
         *         list[CorpusIndexReadWithIds]: the list of corpus indices with IDs
         */
        get: operations["list_corpus_indices_corpus_indices__get"];
        put?: never;
        /**
         * Create Corpus Index
         * @description Create a new corpus index endpoint.
         *     Args:
         *         index_data (CorpusIndexCreate): the data for the new corpus index
         *         session (AsyncSession): the database session
         *         _admin (CorpusIndexAdminDep): the admin dependency
         *     Returns:
         *         CorpusIndexReadWithIds: the created corpus index with IDs
         */
        post: operations["create_corpus_index_corpus_indices__post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/corpus-indices/{index_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Corpus Index
         * @description Get a corpus index by ID endpoint.
         *     Args:
         *         index (AdminCorpusIndexDep): the corpus index dependency
         *         session (SessionDep): the database session
         *     Returns:
         *         CorpusIndexReadWithIds: the corpus index with IDs
         */
        get: operations["get_corpus_index_corpus_indices__index_id__get"];
        put?: never;
        post?: never;
        /**
         * Delete Corpus Index
         * @description Delete a corpus index endpoint.
         *     Args:
         *         index (AdminCorpusIndexDep): the corpus index dependency
         *         session (SessionDep): the database session
         *     Returns:
         *         None
         */
        delete: operations["delete_corpus_index_corpus_indices__index_id__delete"];
        options?: never;
        head?: never;
        /**
         * Update Corpus Index
         * @description Update a corpus index's metadata endpoint.
         *     Args:
         *         index_data (CorpusIndexMetadataUpdate): the metadata update data
         *         index (AdminCorpusIndexDep): the corpus index dependency
         *         session (SessionDep): the database session
         *     Returns:
         *         CorpusIndexReadWithIds: the updated corpus index with IDs
         */
        patch: operations["update_corpus_index_corpus_indices__index_id__patch"];
        trace?: never;
    };
    "/corpus-indices/{index_id}/build-complete": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Mark Corpus Index Built
         * @description Mark a corpus index as built endpoint.
         *     Args:
         *         build_data (CorpusIndexBuildComplete): the build completion data
         *         index (AdminCorpusIndexDep): the corpus index dependency
         *         session (SessionDep): the database session
         *     Returns:
         *         CorpusIndexReadWithIds: the updated corpus index with IDs
         */
        post: operations["mark_corpus_index_built_corpus_indices__index_id__build_complete_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/corpus-indices/{index_id}/copy": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Copy Corpus Index
         * @description Copy a corpus index endpoint.
         *     Args:
         *         copy_data (CorpusIndexCopy): the copy data
         *         source_index (AdminCorpusIndexDep): the source corpus index dependency
         *         session (SessionDep): the database session
         *     Returns:
         *         CorpusIndexReadWithIds: the copied corpus index with IDs
         */
        post: operations["copy_corpus_index_corpus_indices__index_id__copy_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/corpus-indices/{index_id}/indexed-chunks": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Corpus Index Indexed Chunks
         * @description Get a corpus index with its indexed chunks by ID endpoint.
         *     Args:
         *         index (AdminCorpusIndexDep): the corpus index dependency
         *         session (SessionDep): the database session
         *     Returns:
         *         CorpusIndexReadWithIndexedChunks: the corpus index with indexed
         *         chunks
         */
        get: operations["get_corpus_index_indexed_chunks_corpus_indices__index_id__indexed_chunks_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/corpus-indices/{index_id}/status": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /**
         * Update Corpus Index Status
         * @description Update a corpus index's status endpoint.
         *     Args:
         *         status_data (CorpusIndexStatusUpdate): the status update data
         *         index (AdminCorpusIndexDep): the corpus index dependency
         *         session (SessionDep): the database session
         *     Returns:
         *         CorpusIndexReadWithIds: the updated corpus index with IDs
         */
        patch: operations["update_corpus_index_status_corpus_indices__index_id__status_patch"];
        trace?: never;
    };
    "/counterpart-personas/": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Counterpart Personas
         * @description List counterpart personas endpoint.
         *     Args:
         *         session: The database session dependency.
         *         _current_user: The current user dependency.
         *         page: The pagination dependency.
         *         created_by_user_id: Filter by the user who created the persona.
         *         name_contains: Filter by a substring in the persona's name.
         *         used: Filter by whether the persona has been used in simulations.
         *     Returns:
         *         A list of counterpart personas with related simulation IDs.
         */
        get: operations["list_counterpart_personas_counterpart_personas__get"];
        put?: never;
        /**
         * Create Counterpart Persona
         * @description Create a new counterpart persona endpoint.
         *     Args:
         *         persona_data: The data for the new counterpart persona.
         *         session: The database session dependency.
         *         current_user: The current user dependency.
         *     Returns:
         *         The created counterpart persona with related simulation IDs.
         */
        post: operations["create_counterpart_persona_counterpart_personas__post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/counterpart-personas/{persona_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Counterpart Persona
         * @description Get a counterpart persona by ID endpoint.
         *     Args:
         *         persona: The counterpart persona dependency.
         *         session: The database session dependency.
         *     Returns:
         *         The requested counterpart persona with related simulation IDs.
         */
        get: operations["get_counterpart_persona_counterpart_personas__persona_id__get"];
        put?: never;
        post?: never;
        /**
         * Delete Counterpart Persona
         * @description Delete a counterpart persona endpoint.
         *     Args:
         *         persona: The counterpart persona dependency.
         *         session: The database session dependency.
         *     Returns:
         *         None
         *     Raises:
         *         HTTPException: If the delete operation fails due to a ValueError
         *         in the service layer.
         */
        delete: operations["delete_counterpart_persona_counterpart_personas__persona_id__delete"];
        options?: never;
        head?: never;
        /**
         * Update Counterpart Persona
         * @description Update a counterpart persona endpoint.
         *     Args:
         *         persona_data: The data for updating the counterpart persona.
         *         persona: The counterpart persona dependency.
         *         session: The database session dependency.
         *         current_user: The current user dependency.
         *     Returns:
         *         The updated counterpart persona with related simulation IDs.
         */
        patch: operations["update_counterpart_persona_counterpart_personas__persona_id__patch"];
        trace?: never;
    };
    "/counterpart-personas/{persona_id}/copy": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Copy Counterpart Persona
         * @description Copy a counterpart persona endpoint.
         *     Args:
         *         copy_data: The data for copying the counterpart persona.
         *         source_persona: The source counterpart persona dependency.
         *         session: The database session dependency.
         *         current_user: The current user dependency.
         *     Returns:
         *         The copied counterpart persona with related simulation IDs.
         *     Raises:
         *         HTTPException: If the copy operation fails due to a ValueError in the service layer.
         */
        post: operations["copy_counterpart_persona_counterpart_personas__persona_id__copy_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/embeddings/models": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Embedding Models
         * @description List all supported embedding models endpoint.
         *     Args:
         *         _admin: The current admin user performing the operation (for authorization).
         *     Returns:
         *         A list of supported embedding models with their details.
         */
        get: operations["list_embedding_models_embeddings_models_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/indexing-jobs/": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Indexing Jobs
         * @description List indexing jobs endpoint.
         *         Args:
         *             session: The database session.
         *             _admin: The admin dependency.
         *             page: The pagination parameters.
         *             status_filter: Optional status to filter indexing jobs by.
         *             corpus_id: Optional corpus ID to filter indexing jobs by.
         *         Returns:
         *             A list of IndexingJobQueued objects containing the indexing
         *             job data.
         */
        get: operations["list_indexing_jobs_indexing_jobs__get"];
        put?: never;
        /**
         * Create Indexing Job
         * @description Create an indexing job endpoint.
         *         Args:
         *             job_in: The data to create the indexing job with.
         *             session: The database session.
         *             _admin: The admin dependency.
         *         Returns:
         *             An IndexingJobQueued object containing the queued indexing job data.
         *         Raises:
         *             HTTPException: If the indexing job cannot be created due to validation
         *             errors or other constraints, with a 409 status code and error detail.
         */
        post: operations["create_indexing_job_indexing_jobs__post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/indexing-jobs/{job_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Indexing Job Detail
         * @description Get indexing job detail endpoint.
         *         Args:
         *             job_id: The ID of the indexing job to retrieve.
         *             session: The database session.
         *             _admin: The admin dependency.
         *         Returns:
         *             An IndexingJobDetail object containing the indexing job data.
         *         Raises:
         *             HTTPException: If the indexing job is not found, with a 404 status
         *             code and error detail.
         */
        get: operations["get_indexing_job_detail_indexing_jobs__job_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/indexing-jobs/{job_id}/cancel": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Cancel Indexing Job
         * @description Cancel a queued or running indexing job.
         */
        post: operations["cancel_indexing_job_indexing_jobs__job_id__cancel_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/indexing-jobs/active": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Active Indexing Job
         * @description Get the active indexing job endpoint.
         *         Args:
         *             session: The database session.
         *             _admin: The admin dependency.
         *         Returns:
         *             An IndexingJobDetail object containing the active indexing job data,
         *             or a 204 No Content response if no active job is found.
         */
        get: operations["get_active_indexing_job_indexing_jobs_active_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/prompts/": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Prompts
         * @description List prompts with optional filters.
         *     Args:
         *         session (AsyncSession): The database session to use for the query.
         *         _admin_user (User): The current admin user.
         *         page (Page): The pagination parameters.
         *         owner_id (int | None): The ID of the owner to filter prompts by.
         *         is_system (bool | None): Whether to filter prompts by system status.
         *         name_contains (str | None): A substring to filter prompts by name.
         *     Returns:
         *         list[PromptRead]: A list of prompt schemas.
         */
        get: operations["list_prompts_prompts__get"];
        put?: never;
        /**
         * Create Prompt
         * @description Create a new prompt.
         *     Args:
         *         prompt_data (PromptCreate): The data for the new prompt.
         *         session (AsyncSession): The database session to use for the operation.
         *         admin_user (User): The current admin user creating the prompt.
         *     Returns:
         *         PromptRead: The created prompt.
         */
        post: operations["create_prompt_prompts__post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/prompts/{prompt_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Prompt
         * @description Get a prompt by its ID.
         *     Args:
         *         prompt (Prompt): The Prompt model instance to retrieve.
         *     Returns:
         *         PromptRead: The corresponding PromptRead schema instance.
         */
        get: operations["get_prompt_prompts__prompt_id__get"];
        put?: never;
        post?: never;
        /**
         * Delete Prompt
         * @description Delete an existing prompt.
         *     Args:
         *         prompt (Prompt): The Prompt model instance to delete.
         *         session (AsyncSession): The database session to use for the operation.
         *     Returns:
         *         None
         */
        delete: operations["delete_prompt_prompts__prompt_id__delete"];
        options?: never;
        head?: never;
        /**
         * Update Prompt
         * @description Update an existing prompt.
         *     Args:
         *         prompt_data (PromptAdminUpdate): The data to update the prompt with.
         *         prompt (Prompt): The Prompt model instance to update.
         *         session (AsyncSession): The database session to use for the operation.
         *     Returns:
         *         PromptRead: The updated prompt.
         */
        patch: operations["update_prompt_prompts__prompt_id__patch"];
        trace?: never;
    };
    "/prompts/{prompt_id}/copy": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Copy Prompt
         * @description Copy an existing prompt.
         *     Args:
         *         copy_data (PromptClone): The data for the new copied prompt.
         *         source_prompt (Prompt): The Prompt model instance to copy.
         *         session (AsyncSession): The database session to use for the operation.
         *     Returns:
         *         PromptRead: The copied prompt.
         */
        post: operations["copy_prompt_prompts__prompt_id__copy_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/raw-documents/": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Raw Documents
         * @description Endpoint to list raw documents with optional filters and pagination.
         *     Args:
         *         session: The database session to use for the query.
         *         skip: The number of records to skip for pagination.
         *         limit: The maximum number of records to return.
         *         uploaded_by_user_id: Optional filter to return documents uploaded by a specific user.
         *         corpus_id: Optional filter to return documents associated with a specific corpus.
         *         name_contains: Optional filter to return documents whose names contain a specific substring.
         *     Returns:
         *         A list of RawDocument instances matching the filters and pagination criteria.
         */
        get: operations["list_raw_documents_raw_documents__get"];
        put?: never;
        /**
         * Create Raw Document
         * @description Upload and register a new raw document.
         *     Args:
         *         name: Display name for the raw document.
         *         description: Optional description.
         *         corpus_ids: Optional corpora to link during creation.
         *         file: Uploaded PDF source file.
         *         session: The database session to use for the operation.
         *         current_user: The user creating the raw document.
         *     Returns:
         *         The created raw document metadata.
         */
        post: operations["create_raw_document_raw_documents__post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/raw-documents/{raw_document_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Raw Document By Id
         * @description Endpoint to get a raw document by its ID.
         *     Args:
         *         raw_document_id: The ID of the raw document to retrieve.
         *         session: The database session to use for the query.
         *     Returns:
         *         The RawDocument instance if found, else raises a 404 HTTPException.
         */
        get: operations["get_raw_document_by_id_raw_documents__raw_document_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/raw-documents/{raw_document_id}/chunking-profiles/{profile_id}/chunk": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Chunk Raw Document
         * @description Endpoint to chunk an already parsed raw document into document chunks.
         *     Args:
         *         raw_document: The writable raw document to chunk.
         *         chunking_profile: The chunking profile to associate with created chunks.
         *         session: The database session to use for persistence.
         *         options: Query options controlling chunking behavior.
         *     Returns:
         *         A summary of the created or previewed document chunks.
         */
        post: operations["chunk_raw_document_raw_documents__raw_document_id__chunking_profiles__profile_id__chunk_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/raw-documents/{raw_document_id}/chunking-profiles/{profile_id}/ingest": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Ingest Raw Document
         * @description Endpoint to ingest and parse a raw document into document chunks.
         *     Args:
         *         raw_document: The writable raw document to ingest.
         *         chunking_profile: The chunking profile to associate with created chunks.
         *         session: The database session to use for persistence.
         *         options: Query options controlling parsing and chunking.
         *     Returns:
         *         A summary of the created document chunks.
         */
        post: operations["ingest_raw_document_raw_documents__raw_document_id__chunking_profiles__profile_id__ingest_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/scenarios/": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Scenarios
         * @description List scenarios with optional filters.
         *     Args:
         *         session (SessionDep): The database session dependency.
         *         _current_user (CurrentUserDep): The current user dependency (not used in this endpoint but can be used for future enhancements).
         *         skip (int): Number of scenarios to skip for pagination.
         *         limit (int): Maximum number of scenarios to return.
         *         created_by_user_id (int | None): Filter scenarios by creator user ID.
         *         name_contains (str | None): Filter scenarios by name containing this string.
         *         used (bool | None): Filter scenarios by usage status.
         *     Returns:
         *         list[ScenarioPublicReadWithIds]: A list of scenarios matching the filters.
         */
        get: operations["list_scenarios_scenarios__get"];
        put?: never;
        /**
         * Create Scenario
         * @description Create a new scenario endpoint.
         *     Args:
         *         scenario_data (ScenarioCreateRequest): The data for the scenario
         *             to be created.
         *         session (SessionDep): The database session dependency.
         *         current_user (ScenarioCreatorDep): The current user dependency with
         *             scenario creation permissions.
         *     Returns:
         *         ScenarioAuthoringReadWithIds: The created scenario with its IDs.
         */
        post: operations["create_scenario_scenarios__post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/scenarios/{scenario_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Scenario
         * @description Get a scenario by its ID.
         *     Args:
         *         scenario (ScenarioViewerDep): The scenario dependency.
         *         session (SessionDep): The database session dependency.
         *     Returns:
         *         ScenarioPublicReadWithIds: The scenario with its IDs.
         *     Raises:
         *         HTTPException: If the scenario is not found or if there is an error retrieving the scenario.
         */
        get: operations["get_scenario_scenarios__scenario_id__get"];
        put?: never;
        post?: never;
        /**
         * Delete Scenario
         * @description Delete an existing scenario.
         *     Args:
         *         scenario (WritableScenarioDep): The scenario dependency with write
         *             permissions.
         *         session (SessionDep): The database session dependency.
         *     Raises:
         *         HTTPException: If there is an error deleting the scenario.
         */
        delete: operations["delete_scenario_scenarios__scenario_id__delete"];
        options?: never;
        head?: never;
        /**
         * Update Scenario
         * @description Update an existing scenario.
         *     Args:
         *         scenario_data (ScenarioUpdateRequest): The data for updating the
         *             scenario.
         *         scenario (WritableScenarioDep): The scenario dependency with write
         *             permissions.
         *         session (SessionDep): The database session dependency.
         *         current_user (CurrentUserDep): The current user dependency.
         *     Returns:
         *         ScenarioAuthoringReadWithIds: The updated scenario with its IDs.
         */
        patch: operations["update_scenario_scenarios__scenario_id__patch"];
        trace?: never;
    };
    "/scenarios/{scenario_id}/authoring": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Scenario Authoring */
        get: operations["get_scenario_authoring_scenarios__scenario_id__authoring_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/scenarios/{scenario_id}/copy": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Copy Scenario
         * @description Copy an existing scenario.
         *     Args:
         *         copy_data (ScenarioCopyRequest): The data for copying the scenario.
         *         source_scenario (ScenarioViewerDep): The source scenario dependency.
         *         session (SessionDep): The database session dependency.
         *         current_user (ScenarioCreatorDep): The current user dependency with
         *             scenario creation permissions.
         *     Returns:
         *         ScenarioAuthoringReadWithIds: The copied scenario with its IDs.
         *     Raises:
         *         HTTPException: If there is an error copying the scenario.
         */
        post: operations["copy_scenario_scenarios__scenario_id__copy_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/scenarios/generate-context": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Generate Scenario Context */
        post: operations["generate_scenario_context_scenarios_generate_context_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/sessions/": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Sessions
         * @description List sessions with optional filters.
         *     Args:
         *         session (SessionDep): The database session dependency.
         *         _admin_user (AdminDep): The admin user dependency.
         *         page (Page): The pagination parameters.
         *         user_id (int | None): The ID of the user to filter sessions by.
         *         active (bool | None): Whether to filter for active sessions.
         *         expired (bool | None): Whether to filter for expired sessions.
         *     Returns:
         *         list[SessionRead]: A list of session schemas.
         */
        get: operations["list_sessions_sessions__get"];
        put?: never;
        /**
         * Create Session
         * @description Create a new session endpoint.
         *     Args:
         *         session_data (SessionCreateRequest): The session data to create.
         *         session (SessionDep): The database session dependency.
         *         admin_user (AdminDep): The admin user dependency.
         *     Returns:
         *         SessionRead: The created session.
         */
        post: operations["create_session_sessions__post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/sessions/{session_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Session
         * @description Get a session by its ID.
         *     Args:
         *         user_session (AdminSessionDep): The admin session dependency.
         *     Returns:
         *         SessionRead: The session schema.
         */
        get: operations["get_session_sessions__session_id__get"];
        put?: never;
        post?: never;
        /**
         * Delete Session
         * @description Delete a session.
         *     Args:
         *         user_session (AdminSessionDep): The admin session dependency.
         *         session (SessionDep): The database session dependency.
         *     Returns:
         *         None
         */
        delete: operations["delete_session_sessions__session_id__delete"];
        options?: never;
        head?: never;
        /**
         * Update Session
         * @description Update a session by its ID.
         *     Args:
         *         session_data (SessionUpdateRequest): The session data to update.
         *         user_session (AdminSessionDep): The admin session dependency.
         *         session (SessionDep): The database session dependency.
         *     Returns:
         *         SessionRead: The updated session.
         */
        patch: operations["update_session_sessions__session_id__patch"];
        trace?: never;
    };
    "/sessions/{session_id}/end": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * End Session
         * @description End a session.
         *     Args:
         *         end_data (SessionEnd): The end session data.
         *         user_session (AdminSessionDep): The admin session dependency.
         *         session (SessionDep): The database session dependency.
         *     Returns:
         *         SessionRead: The updated session.
         */
        post: operations["end_session_sessions__session_id__end_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/sessions/{session_id}/heartbeat": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Heartbeat Session
         * @description Send a heartbeat for a session.
         *     Args:
         *         heartbeat_data (SessionHeartbeat): The heartbeat data.
         *         user_session (AdminSessionDep): The admin session dependency.
         *         session (SessionDep): The database session dependency.
         *     Returns:
         *         SessionRead: The updated session.
         */
        post: operations["heartbeat_session_sessions__session_id__heartbeat_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/simulations/": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Simulations */
        get: operations["list_simulations_simulations__get"];
        put?: never;
        /**
         * Create Simulation
         * @description Create a new simulation.
         *     Args:
         *         simulation_data: The data for creating the simulation.
         *         session: The database session.
         *         current_user: The user creating the simulation.
         *     Returns:
         *         A SimulationRead containing the created simulation.
         *     Raises:
         *         ValueError: If the simulation cannot be created.
         */
        post: operations["create_simulation_simulations__post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/simulations/{simulation_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Simulation
         * @description Get a simulation by its ID.
         *     Args:
         *         simulation: The simulation instance.
         *     Returns:
         *         A SimulationReadWithState containing the simulation data.
         */
        get: operations["get_simulation_simulations__simulation_id__get"];
        put?: never;
        post?: never;
        /**
         * Delete Simulation
         * @description Delete a simulation by its ID.
         *     Args:
         *         simulation: The simulation instance.
         *         session: The database session.
         *     Returns:
         *         None
         *     Raises:
         *         ValueError: If the simulation cannot be deleted.
         */
        delete: operations["delete_simulation_simulations__simulation_id__delete"];
        options?: never;
        head?: never;
        /**
         * Update Simulation
         * @description Update a simulation by its ID.
         *     Args:
         *         simulation_data: The data for updating the simulation.
         *         simulation: The simulation instance.
         *         session: The database session.
         *     Returns:
         *         A SimulationRead containing the updated simulation.
         *     Raises:
         *         ValueError: If the simulation cannot be updated.
         */
        patch: operations["update_simulation_simulations__simulation_id__patch"];
        trace?: never;
    };
    "/simulations/{simulation_id}/cancel": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Cancel Simulation
         * @description Cancel a simulation by its ID.
         *     Args:
         *         simulation: The simulation instance.
         *         session: The database session.
         *     Returns:
         *         A SimulationRead containing the updated simulation.
         */
        post: operations["cancel_simulation_simulations__simulation_id__cancel_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/simulations/{simulation_id}/proxy-turn": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Submit Simulation Proxy Turn
         * @description Submit a proxy turn for a simulation.
         *     Args:
         *         proxy_data: The data for the proxy turn.
         *         simulation: The simulation instance.
         *         session: The database session.
         *         current_user: The user submitting the proxy turn.
         *     Returns:
         *         A SimulationProxyTurnResponse containing the result of the
         *         proxy turn.
         *     Raises:
         *         ValueError: If the proxy turn cannot be submitted.
         */
        post: operations["submit_simulation_proxy_turn_simulations__simulation_id__proxy_turn_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/simulations/{simulation_id}/proxy/disable": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Disable Simulation Proxy
         * @description Disable the proxy for a simulation.
         *     Args:
         *         simulation: The simulation instance.
         *         session: The database session.
         *         current_user: The user disabling the proxy.
         *     Returns:
         *         A SimulationProxyDisableResponse containing the result of the
         *         proxy disable action.
         *     Raises:
         *         ValueError: If the proxy cannot be disabled.
         */
        post: operations["disable_simulation_proxy_simulations__simulation_id__proxy_disable_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/simulations/{simulation_id}/review": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Review Simulation
         * @description Review a simulation as a teacher.
         *     Args:
         *         review_data: The data for the teacher review, including feedback.
         *         simulation: The simulation instance to review.
         *         session: The database session.
         *         current_teacher: The teacher submitting the review.
         *     Returns:
         *         A SimulationRead containing the updated simulation with the review.
         *     Raises:
         *         ValueError: If the current user is not a teacher or if the review
         *         cannot be submitted due to the simulation's current status.
         */
        post: operations["review_simulation_simulations__simulation_id__review_post"];
        /** Delete Review Simulation */
        delete: operations["delete_review_simulation_simulations__simulation_id__review_delete"];
        options?: never;
        head?: never;
        /** Update Review Simulation */
        patch: operations["update_review_simulation_simulations__simulation_id__review_patch"];
        trace?: never;
    };
    "/simulations/{simulation_id}/start": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Start Simulation
         * @description Start a simulation.
         *     Args:
         *         start_data: The data for starting the simulation.
         *         simulation: The simulation instance.
         *         session: The database session.
         *         current_user: The user starting the simulation.
         *     Returns:
         *         A SimulationReadWithState containing the updated simulation state.
         *     Raises:
         *         ValueError: If the simulation cannot be started.
         */
        post: operations["start_simulation_simulations__simulation_id__start_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/simulations/{simulation_id}/state": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Simulation State
         * @description Get the current state of a simulation.
         *     Args:
         *         simulation: The simulation instance.
         *     Returns:
         *         A SimulationReadWithState containing the current simulation state.
         *     Raises:
         *         ValueError: If the simulation state cannot be retrieved.
         */
        get: operations["get_simulation_state_simulations__simulation_id__state_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/simulations/{simulation_id}/turn": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Submit Simulation Turn
         * @description Submit a turn for a simulation.
         *     Args:
         *         turn_data: The data for the simulation turn.
         *         simulation: The simulation instance.
         *         session: The database session.
         *         current_user: The user submitting the turn.
         *     Returns:
         *         A SimulationTurnResponse containing the result of the turn.
         *     Raises:
         *         ValueError: If the turn cannot be submitted.
         */
        post: operations["submit_simulation_turn_simulations__simulation_id__turn_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/simulations/completed": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Completed Simulations */
        get: operations["list_completed_simulations_simulations_completed_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/simulations/reviews": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Reviewed Simulations */
        get: operations["list_reviewed_simulations_simulations_reviews_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/users/": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get All Users
         * @description Get a list of all users. Admins only.
         *     Args:
         *         session (SessionDep): The database session for any necessary queries.
         *         admin_user (AdminDep): The current admin user performing the operation.
         *         page (Page): Pagination parameters containing skip and limit.
         *     Returns:
         *         list[UserRead]: A list of user information.
         *     Raises:
         *         PermissionError: If the current user is not an admin.
         *         ValueError: If there is an error retrieving the users.
         */
        get: operations["get_all_users_users__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/users/{user_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        /**
         * Delete User
         * @description Delete a user. Admins only.
         *     Args:
         *         user_id (int): The ID of the user to delete.
         *         session (SessionDep): The database session for any necessary queries.
         *         admin_user (AdminDep): The current admin user performing the operation.
         *     Raises:
         *         HTTPException: If the user is not found or if there is an error deleting the user.
         */
        delete: operations["delete_user_users__user_id__delete"];
        options?: never;
        head?: never;
        /**
         * Update User
         * @description Update user information. Admins only.
         *     Args:
         *         user_id (int): The ID of the user to update.
         *         user_data (UserUpdate): The data to update the user with.
         *         session (SessionDep): The database session for any necessary queries.
         *         admin_user (AdminDep): The current admin user performing the operation.
         *     Returns:
         *         UserRead: The updated user information.
         *     Raises:
         *         HTTPException: If the user is not found or if there is an error updating the user.
         */
        patch: operations["update_user_users__user_id__patch"];
        trace?: never;
    };
    "/users/{username}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get User By Username
         * @description Get user information by username. Admins only.
         *     Args:
         *         username (str): The username of the user to retrieve.
         *         session (SessionDep): The database session for any necessary queries.
         *         _admin_user (AdminDep): The current admin user performing the
         *             operation (not used but required for admin check).
         *     Returns:
         *         UserRead: The user information.
         *     Raises:
         *         HTTPException: If the user is not found or if there is an error retrieving the user
         */
        get: operations["get_user_by_username_users__username__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/users/login": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Login
         * @description Authenticate user and return an access token.
         *     Args:
         *         form_data (OAuth2PasswordRequestForm): The form data containing the username and password.
         *         session (SessionDep): The database session for any necessary queries.
         *     Returns:
         *         Token: The access token and token type.
         *     Raises:
         *         HTTPException: If the username or password is invalid.
         */
        post: operations["login_users_login_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/users/me": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Me User
         * @description Get the current authenticated user's information.
         *     Args:
         *         current_user (CurrentUserDep): The current authenticated user.
         *     Returns:
         *         UserRead: The current user's information.
         */
        get: operations["get_me_user_users_me_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/users/me/password": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /**
         * Change Own Password
         * @description Change the current user's password after verifying the old password.
         *     Args:
         *         password_data (UserPasswordChange): The data for the password change.
         *         session (SessionDep): The database session for any necessary queries.
         *         current_user (CurrentUserDep): The current authenticated user.
         *     Returns:
         *         UserRead: The updated user information.
         */
        patch: operations["change_own_password_users_me_password_patch"];
        trace?: never;
    };
    "/users/register": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Create User
         * @description Create a new user. Admins only.
         *     Args:
         *         user_data (UserCreate): The data for the new user.
         *         session (SessionDep): The database session for any necessary queries.
         *         admin_user (AdminDep): The current admin user performing the operation.
         *     Returns:
         *         UserCreatedResponse: The response containing the created user.
         */
        post: operations["create_user_users_register_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/users/roles": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Roles
         * @description List available roles for admin user-management forms.
         */
        get: operations["list_roles_users_roles_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/vector-stores/": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Vector Stores
         * @description List vector stores with optional filtering by backend and whether they
         *     have associated corpus indices.
         *         Args:
         *             session: The database session.
         *             page: The pagination parameters.
         *             backend: Optional backend filter.
         *             has_indexes: Optional filter to include only vector stores with
         *                 or without corpus indices.
         *         Returns:
         *             A list of VectorStoreReadWithIds objects containing the vector
         *             store data and associated corpus index IDs.
         */
        get: operations["list_vector_stores_vector_stores__get"];
        put?: never;
        /**
         * Create Vector Store
         * @description Create a new vector store endpoint.
         *     Args:
         *         vector_store_data: The data to create the vector store with.
         *         session: The database session.
         *         _admin: The admin dependency.
         *     Returns:
         *         A VectorStoreReadWithIds object containing the created
         *         vector store data and associated corpus index IDs.
         */
        post: operations["create_vector_store_vector_stores__post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/vector-stores/{vector_store_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Vector Store
         * @description Get a vector store by ID.
         *          Args:
         *             vector_store: The vector store to get (injected by dependency).
         *             session: The database session.
         *         Returns:
         *             A VectorStoreReadWithIds object containing the vector store
         *             data and associated corpus index IDs.
         */
        get: operations["get_vector_store_vector_stores__vector_store_id__get"];
        put?: never;
        post?: never;
        /**
         * Delete Vector Store
         * @description Vector store delete endpoint.
         *         Args:
         *             vector_store: The vector store to delete (injected by dependency).
         *             session: The database session.
         *         Returns:
         *             None
         *         Raises:
         *             HTTPException: If the vector store has associated corpus indices.
         */
        delete: operations["delete_vector_store_vector_stores__vector_store_id__delete"];
        options?: never;
        head?: never;
        /**
         * Update Vector Store
         * @description Update a vector store by ID.
         *         Args:
         *             vector_store_data: The data to update the vector store with.
         *             vector_store: The vector store to update (injected by dependency).
         *             session: The database session.
         *         Returns:
         *             A VectorStoreReadWithIds object containing the updated vector store
         *             data and associated corpus index IDs.
         */
        patch: operations["update_vector_store_vector_stores__vector_store_id__patch"];
        trace?: never;
    };
    "/vector-stores/{vector_store_id}/connection": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /**
         * Update Vector Store Connection
         * @description Update the connection details of a vector store by ID.
         *         Args:
         *             connection_data: The connection data to update the vector
         *                 store with.
         *             vector_store: The vector store to update (injected by dependency).
         *             session: The database session.
         *         Returns:
         *             A VectorStoreReadWithIds object containing the updated vector store
         *             data and associated corpus index IDs.
         */
        patch: operations["update_vector_store_connection_vector_stores__vector_store_id__connection_patch"];
        trace?: never;
    };
};
export type webhooks = Record<string, never>;
export type components = {
    schemas: {
        /** Body_create_raw_document_raw_documents__post */
        Body_create_raw_document_raw_documents__post: {
            /**
             * Corpus Ids
             * @default []
             */
            corpus_ids: number[];
            /** Description */
            description?: string | null;
            /** File */
            file: string;
            /** Name */
            name: string;
        };
        /** Body_login_users_login_post */
        Body_login_users_login_post: {
            /** Client Id */
            client_id?: string | null;
            /**
             * Client Secret
             * Format: password
             */
            client_secret?: string | null;
            /** Grant Type */
            grant_type?: string | null;
            /**
             * Password
             * Format: password
             */
            password: string;
            /**
             * Scope
             * @default
             */
            scope: string;
            /** Username */
            username: string;
        };
        /** ChunkerDefinitionRead */
        ChunkerDefinitionRead: {
            /** Fields */
            fields?: components["schemas"]["ChunkerFieldDefinitionRead"][];
            /** Label */
            label: string;
            /** Strategy */
            strategy: string;
            /** Supports Ingestion */
            supports_ingestion: boolean;
        };
        /** ChunkerFieldDefinitionRead */
        ChunkerFieldDefinitionRead: {
            /** Default */
            default: unknown;
            /** Help Text */
            help_text?: string | null;
            /**
             * Kind
             * @enum {string}
             */
            kind: "int" | "string" | "string_list";
            /** Label */
            label: string;
            /** Maximum */
            maximum?: number | null;
            /** Minimum */
            minimum?: number | null;
            /** Name */
            name: string;
            /** Required */
            required: boolean;
        };
        /** ChunkingProfileCopy */
        ChunkingProfileCopy: {
            /** Config */
            config?: {
                [key: string]: unknown;
            } | null;
            /** Chunking profile name */
            name: string;
            /** Chunking strategy */
            strategy?: string | null;
        };
        /** ChunkingProfileCreate */
        ChunkingProfileCreate: {
            /** Config */
            config?: {
                [key: string]: unknown;
            };
            /** Chunking profile name */
            name: string;
            /** Chunking strategy */
            strategy: string;
        };
        /** ChunkingProfileReadWithIds */
        ChunkingProfileReadWithIds: {
            /** Config */
            config?: {
                [key: string]: unknown;
            };
            /** Corpus Index Ids */
            corpus_index_ids?: number[];
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Document Chunk Ids */
            document_chunk_ids?: number[];
            /** Id */
            id: number;
            /**
             * Last Updated
             * Format: date-time
             */
            last_updated: string;
            /** Chunking profile name */
            name: string;
            /** Chunking strategy */
            strategy: string;
        };
        /** ChunkingProfileUpdate */
        ChunkingProfileUpdate: {
            /** Config */
            config?: {
                [key: string]: unknown;
            } | null;
            /** Chunking profile name */
            name?: string | null;
            /** Chunking strategy */
            strategy?: string | null;
        };
        /** ChunkPreview */
        ChunkPreview: {
            /** Chunk Index */
            chunk_index: number;
            /** Chunk Metadata */
            chunk_metadata?: {
                [key: string]: unknown;
            };
            /** Content */
            content: string;
        };
        /** CorpusChunkResult */
        CorpusChunkResult: {
            /** Chunker */
            chunker: string;
            /** Chunking Profile Id */
            chunking_profile_id: number;
            /**
             * Chunks Created
             * @default 0
             */
            chunks_created: number;
            /** Corpus Id */
            corpus_id: number;
            /**
             * Preview
             * @default false
             */
            preview: boolean;
            /** Raw Documents */
            raw_documents?: components["schemas"]["RawDocumentChunkResult"][];
        };
        /** CorpusCreate */
        CorpusCreate: {
            /** Description */
            description?: string | null;
            /** Corpus name */
            name: string;
            /** Raw Document Ids */
            raw_document_ids?: number[];
        };
        /** CorpusEmbeddingBuildQueued */
        CorpusEmbeddingBuildQueued: {
            /** Chunking Profile Id */
            chunking_profile_id: number;
            /** Corpus Id */
            corpus_id: number;
            /** Corpus Index Id */
            corpus_index_id: number;
            /** Embedding Dimensions */
            embedding_dimensions: number;
            /** Embedding Model */
            embedding_model: string;
            /** Indexed Chunks Url */
            indexed_chunks_url?: string | null;
            /** Poll Url */
            poll_url?: string | null;
            /**
             * Status
             * @default building
             */
            status: string;
            /** Vector Namespace */
            vector_namespace: string;
            /** Vector Store Id */
            vector_store_id: number;
        };
        /** CorpusEmbeddingBuildRequest */
        CorpusEmbeddingBuildRequest: {
            /** Embedding model */
            embedding_model: string;
            /** Corpus index name */
            name: string;
            /** Vector Namespace */
            vector_namespace?: string | null;
        };
        /** CorpusEmbeddingBuildResult */
        CorpusEmbeddingBuildResult: {
            /** Built At */
            built_at?: string | null;
            /** Chunking Profile Id */
            chunking_profile_id: number;
            /**
             * Chunks Indexed
             * @default 0
             */
            chunks_indexed: number;
            /** Corpus Id */
            corpus_id: number;
            /** Corpus Index Id */
            corpus_index_id: number;
            /** Embedding Dimensions */
            embedding_dimensions: number;
            /** Embedding Model */
            embedding_model: string;
            /** Indexed Chunks */
            indexed_chunks?: components["schemas"]["IndexedChunkBuildRef"][];
            /** Status */
            status: string;
            /** Store Metadata */
            store_metadata?: {
                [key: string]: unknown;
            };
            /** Vector Namespace */
            vector_namespace: string;
            /** Vector Store Id */
            vector_store_id: number;
        };
        /** CorpusIndexBuildComplete */
        CorpusIndexBuildComplete: {
            /**
             * Built At
             * Format: date-time
             */
            built_at: string;
            /** Embedding Dimensions */
            embedding_dimensions?: number | null;
            /**
             * Corpus index status
             * @default built
             */
            status: string;
            /** Vector Namespace */
            vector_namespace?: string | null;
        };
        /** CorpusIndexCopy */
        CorpusIndexCopy: {
            /** Chunking Profile Id */
            chunking_profile_id?: number | null;
            /** Corpus Id */
            corpus_id?: number | null;
            /** Embedding Dimensions */
            embedding_dimensions?: number | null;
            /** Embedding model */
            embedding_model?: string | null;
            /** Corpus index name */
            name: string;
            /** Vector Namespace */
            vector_namespace?: string | null;
            /** Vector Store Id */
            vector_store_id?: number | null;
        };
        /** CorpusIndexCreate */
        CorpusIndexCreate: {
            /** Chunking Profile Id */
            chunking_profile_id: number;
            /** Corpus Id */
            corpus_id: number;
            /** Embedding Dimensions */
            embedding_dimensions?: number | null;
            /** Embedding model */
            embedding_model: string;
            /** Corpus index name */
            name: string;
            /**
             * Corpus index status
             * @default created
             */
            status: string;
            /** Vector Namespace */
            vector_namespace?: string | null;
            /** Vector Store Id */
            vector_store_id: number;
        };
        /** CorpusIndexIndexedChunkRead */
        CorpusIndexIndexedChunkRead: {
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Document Chunk Id */
            document_chunk_id: number;
            /** External Vector Id */
            external_vector_id?: string | null;
        };
        /** CorpusIndexMetadataUpdate */
        CorpusIndexMetadataUpdate: {
            /** Embedding Dimensions */
            embedding_dimensions?: number | null;
            /** Embedding model */
            embedding_model?: string | null;
            /** Corpus index name */
            name?: string | null;
            /** Vector Namespace */
            vector_namespace?: string | null;
        };
        /** CorpusIndexReadWithIds */
        CorpusIndexReadWithIds: {
            /** Build Error */
            build_error?: string | null;
            /** Built At */
            built_at?: string | null;
            /** Chunking Profile Id */
            chunking_profile_id: number;
            /** Corpus Id */
            corpus_id: number;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Embedding Dimensions */
            embedding_dimensions?: number | null;
            /** Embedding model */
            embedding_model: string;
            /** Id */
            id: number;
            /** Indexed Document Chunk Ids */
            indexed_document_chunk_ids?: number[];
            /**
             * Last Updated
             * Format: date-time
             */
            last_updated: string;
            /** Corpus index name */
            name: string;
            /** Status */
            status: string;
            /** Vector Namespace */
            vector_namespace?: string | null;
            /** Vector Store Id */
            vector_store_id: number;
        };
        /** CorpusIndexReadWithIndexedChunks */
        CorpusIndexReadWithIndexedChunks: {
            /** Build Error */
            build_error?: string | null;
            /** Built At */
            built_at?: string | null;
            /** Chunking Profile Id */
            chunking_profile_id: number;
            /** Corpus Id */
            corpus_id: number;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Embedding Dimensions */
            embedding_dimensions?: number | null;
            /** Embedding model */
            embedding_model: string;
            /** Id */
            id: number;
            /** Indexed Chunks */
            indexed_chunks?: components["schemas"]["CorpusIndexIndexedChunkRead"][];
            /**
             * Last Updated
             * Format: date-time
             */
            last_updated: string;
            /** Corpus index name */
            name: string;
            /** Status */
            status: string;
            /** Vector Namespace */
            vector_namespace?: string | null;
            /** Vector Store Id */
            vector_store_id: number;
        };
        /** CorpusIndexStatusUpdate */
        CorpusIndexStatusUpdate: {
            /** Corpus index status */
            status: string;
        };
        /** CorpusIngestResult */
        CorpusIngestResult: {
            /** Chunking Profile Id */
            chunking_profile_id: number;
            /** Chunks Created */
            chunks_created: number;
            /** Corpus Id */
            corpus_id: number;
            /** Raw Documents */
            raw_documents?: components["schemas"]["RawDocumentIngestResult"][];
        };
        /** CorpusRead */
        CorpusRead: {
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Created By User Id */
            created_by_user_id: number;
            /** Description */
            description?: string | null;
            /** Id */
            id: number;
            /** Last Edit By User Id */
            last_edit_by_user_id?: number | null;
            /** Corpus name */
            name: string;
        };
        /** CounterpartPersonaCopyRequest */
        CounterpartPersonaCopyRequest: {
            /** Description */
            description?: string | null;
            /** Counterpart persona name */
            name: string;
        };
        /** CounterpartPersonaCreateRequest */
        CounterpartPersonaCreateRequest: {
            /** Description */
            description?: string | null;
            /** Counterpart persona name */
            name: string;
        };
        /** CounterpartPersonaReadWithIds */
        CounterpartPersonaReadWithIds: {
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Created By User Id */
            created_by_user_id: number;
            /** Description */
            description?: string | null;
            /** Id */
            id: number;
            /** Last Edit By User Id */
            last_edit_by_user_id?: number | null;
            /**
             * Last Updated
             * Format: date-time
             */
            last_updated: string;
            /** Counterpart persona name */
            name: string;
            /** Simulation Ids */
            simulation_ids?: number[];
        };
        /** CounterpartPersonaUpdateRequest */
        CounterpartPersonaUpdateRequest: {
            /** Description */
            description?: string | null;
            /** Counterpart persona name */
            name?: string | null;
        };
        /** EmbeddingModelRead */
        EmbeddingModelRead: {
            /** Dimensionality */
            dimensionality: number;
            /** Display Name */
            display_name: string;
            /** Name */
            name: string;
            /**
             * Normalized
             * @default false
             */
            normalized: boolean;
            /** Provider */
            provider: string;
        };
        /** HTTPValidationError */
        HTTPValidationError: {
            /** Detail */
            detail?: components["schemas"]["ValidationError"][];
        };
        /** IndexedChunkBuildRef */
        IndexedChunkBuildRef: {
            /** Document Chunk Id */
            document_chunk_id: number;
            /** External Vector Id */
            external_vector_id: string;
        };
        /** IndexingJobCreate */
        IndexingJobCreate: {
            /** Chunking Profile Id */
            chunking_profile_id: number;
            /** Corpus Id */
            corpus_id: number;
            /** Embedding Model */
            embedding_model: string;
            /** Requested Index Name */
            requested_index_name: string;
            /** Requested Vector Namespace */
            requested_vector_namespace?: string | null;
            /**
             * Stage
             * @default validating
             */
            stage: string;
            /**
             * Status
             * @default queued
             */
            status: string;
            /** Vector Store Id */
            vector_store_id: number;
        };
        /** IndexingJobDetail */
        IndexingJobDetail: {
            /**
             * Cancel Requested
             * @default false
             */
            cancel_requested: boolean;
            /** Candidate Corpus Index Id */
            candidate_corpus_index_id?: number | null;
            /** Chunking Profile Id */
            chunking_profile_id: number;
            /** Chunks Created */
            chunks_created: number;
            /** Chunks Indexed */
            chunks_indexed: number;
            /** Completed At */
            completed_at?: string | null;
            /** Corpus Id */
            corpus_id: number;
            /** Current Document Name */
            current_document_name?: string | null;
            /** Current Raw Document Id */
            current_raw_document_id?: number | null;
            /** Embedding Model */
            embedding_model: string;
            /** Failure Detail */
            failure_detail?: string | null;
            /** Id */
            id: number;
            /** Processed Documents */
            processed_documents: number;
            /**
             * Queued At
             * Format: date-time
             */
            queued_at: string;
            /** Replaced Corpus Index Id */
            replaced_corpus_index_id?: number | null;
            /** Requested Index Name */
            requested_index_name: string;
            /** Requested Vector Namespace */
            requested_vector_namespace?: string | null;
            /** Stage */
            stage: string;
            /** Started At */
            started_at?: string | null;
            /** Status */
            status: string;
            /** Total Documents */
            total_documents: number;
            /** Vector Store Id */
            vector_store_id: number;
            /** Warnings */
            warnings?: components["schemas"]["IndexingJobWarningRead"][];
        };
        /** IndexingJobQueued */
        IndexingJobQueued: {
            /**
             * Cancel Requested
             * @default false
             */
            cancel_requested: boolean;
            /** Candidate Corpus Index Id */
            candidate_corpus_index_id?: number | null;
            /** Chunking Profile Id */
            chunking_profile_id: number;
            /** Chunks Created */
            chunks_created: number;
            /** Chunks Indexed */
            chunks_indexed: number;
            /** Completed At */
            completed_at?: string | null;
            /** Corpus Id */
            corpus_id: number;
            /** Current Document Name */
            current_document_name?: string | null;
            /** Current Raw Document Id */
            current_raw_document_id?: number | null;
            /** Embedding Model */
            embedding_model: string;
            /** Failure Detail */
            failure_detail?: string | null;
            /** Id */
            id: number;
            /** Processed Documents */
            processed_documents: number;
            /**
             * Queued At
             * Format: date-time
             */
            queued_at: string;
            /** Replaced Corpus Index Id */
            replaced_corpus_index_id?: number | null;
            /** Requested Index Name */
            requested_index_name: string;
            /** Requested Vector Namespace */
            requested_vector_namespace?: string | null;
            /** Stage */
            stage: string;
            /** Started At */
            started_at?: string | null;
            /** Status */
            status: string;
            /** Total Documents */
            total_documents: number;
            /** Vector Store Id */
            vector_store_id: number;
        };
        /** IndexingJobWarningRead */
        IndexingJobWarningRead: {
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Document Name */
            document_name?: string | null;
            /** Id */
            id: number;
            /** Message */
            message: string;
            /** Raw Document Id */
            raw_document_id?: number | null;
            /** Stage */
            stage: string;
        };
        /** NegotiationStateSchema */
        NegotiationStateSchema: {
            /** Current Phase */
            current_phase?: string | null;
            /** Data */
            data?: {
                [key: string]: unknown;
            };
            /** User Side */
            user_side?: ("side_a" | "side_b") | null;
        };
        /** PromptAdminUpdate */
        PromptAdminUpdate: {
            /** Description */
            description?: string | null;
            /** Is System */
            is_system?: boolean | null;
            /** Messages */
            messages?: {
                [key: string]: unknown;
            } | null;
            /** Prompt name */
            name?: string | null;
            /** Owner Id */
            owner_id?: number | null;
        };
        /** PromptClone */
        PromptClone: {
            /** Description */
            description?: string | null;
            /** Prompt name */
            name: string;
            /** Owner Id */
            owner_id: number;
        };
        /** PromptCreate */
        PromptCreate: {
            /** Description */
            description?: string | null;
            /**
             * Is System
             * @default false
             */
            is_system: boolean;
            /** Messages */
            messages?: {
                [key: string]: unknown;
            };
            /** Prompt name */
            name: string;
            /** Owner Id */
            owner_id?: number | null;
        };
        /** PromptRead */
        PromptRead: {
            /** Description */
            description?: string | null;
            /** Id */
            id: number;
            /** Is System */
            is_system: boolean;
            /** Messages */
            messages?: {
                [key: string]: unknown;
            };
            /** Prompt name */
            name: string;
            /** Owner Id */
            owner_id?: number | null;
        };
        /** RawDocumentChunkResult */
        RawDocumentChunkResult: {
            /** Chunk Ids */
            chunk_ids?: number[];
            /** Chunker */
            chunker: string;
            /** Chunking Profile Id */
            chunking_profile_id: number;
            /** Chunks */
            chunks?: components["schemas"]["ChunkPreview"][];
            /**
             * Chunks Created
             * @default 0
             */
            chunks_created: number;
            /**
             * Preview
             * @default false
             */
            preview: boolean;
            /** Raw Document Id */
            raw_document_id: number;
        };
        /** RawDocumentIngestResult */
        RawDocumentIngestResult: {
            /** Chunk Ids */
            chunk_ids?: number[];
            /** Chunking Profile Id */
            chunking_profile_id: number;
            /** Chunks Created */
            chunks_created: number;
            /** Raw Document Id */
            raw_document_id: number;
        };
        /** RawDocumentRead */
        RawDocumentRead: {
            /** Description */
            description?: string | null;
            /** Id */
            id: number;
            /** Raw document name */
            name: string;
            /** Parsed At */
            parsed_at?: string | null;
            /** Source Hash */
            source_hash?: string | null;
            /** Source Mtime */
            source_mtime?: string | null;
            /** Raw document source path */
            source_path: string;
            /** Source Size */
            source_size?: number | null;
            /**
             * Source Status
             * @default unverified
             * @enum {string}
             */
            source_status: "available" | "missing" | "changed" | "unverified" | "error";
            /**
             * Uploaded At
             * Format: date-time
             */
            uploaded_at: string;
            /** Uploaded By User Id */
            uploaded_by_user_id: number;
        };
        /** RoleRead */
        RoleRead: {
            /** Id */
            id: number;
            /** Name */
            name: string;
        };
        /** ScenarioAuthoringReadWithIds */
        ScenarioAuthoringReadWithIds: {
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Created By User Id */
            created_by_user_id: number;
            /** Description */
            description?: string | null;
            /** Id */
            id: number;
            /** Last Edit By User Id */
            last_edit_by_user_id?: number | null;
            /**
             * Last Updated
             * Format: date-time
             */
            last_updated: string;
            /** Scenario name */
            name: string;
            /** Public Context */
            public_context?: {
                [key: string]: unknown;
            };
            /** Side A Private Context */
            side_a_private_context?: {
                [key: string]: unknown;
            };
            /** Side B Private Context */
            side_b_private_context?: {
                [key: string]: unknown;
            };
            /** Simulation Ids */
            simulation_ids?: number[];
        };
        /** ScenarioContextGenerateRequest */
        ScenarioContextGenerateRequest: {
            /** Scenario description */
            description: string;
            /** Scenario name */
            name: string;
        };
        /** ScenarioContextGenerateResponse */
        ScenarioContextGenerateResponse: {
            /** Public Context */
            public_context?: {
                [key: string]: unknown;
            };
            /** Side A Private Context */
            side_a_private_context?: {
                [key: string]: unknown;
            };
            /** Side B Private Context */
            side_b_private_context?: {
                [key: string]: unknown;
            };
        };
        /** ScenarioCopyRequest */
        ScenarioCopyRequest: {
            /** Description */
            description?: string | null;
            /** Scenario name */
            name: string;
        };
        /** ScenarioCreateRequest */
        ScenarioCreateRequest: {
            /** Description */
            description?: string | null;
            /** Scenario name */
            name: string;
            /** Public Context */
            public_context?: {
                [key: string]: unknown;
            };
            /** Side A Private Context */
            side_a_private_context?: {
                [key: string]: unknown;
            };
            /** Side B Private Context */
            side_b_private_context?: {
                [key: string]: unknown;
            };
        };
        /** ScenarioPublicReadWithIds */
        ScenarioPublicReadWithIds: {
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Created By User Id */
            created_by_user_id: number;
            /** Id */
            id: number;
            /** Last Edit By User Id */
            last_edit_by_user_id?: number | null;
            /**
             * Last Updated
             * Format: date-time
             */
            last_updated: string;
            /** Scenario name */
            name: string;
            /** Public Context */
            public_context?: {
                [key: string]: unknown;
            };
            /** Simulation Ids */
            simulation_ids?: number[];
        };
        /** ScenarioUpdateRequest */
        ScenarioUpdateRequest: {
            /** Description */
            description?: string | null;
            /** Scenario name */
            name?: string | null;
            /** Public Context */
            public_context?: {
                [key: string]: unknown;
            } | null;
            /** Side A Private Context */
            side_a_private_context?: {
                [key: string]: unknown;
            } | null;
            /** Side B Private Context */
            side_b_private_context?: {
                [key: string]: unknown;
            } | null;
        };
        /** SessionCreateRequest */
        SessionCreateRequest: {
            /** Expires At */
            expires_at?: string | null;
            /** User Id */
            user_id?: number | null;
        };
        /** SessionEnd */
        SessionEnd: {
            /** Ended At */
            ended_at?: string | null;
        };
        /** SessionHeartbeat */
        SessionHeartbeat: {
            /** Last Seen At */
            last_seen_at?: string | null;
        };
        /** SessionRead */
        SessionRead: {
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Ended At */
            ended_at?: string | null;
            /** Expires At */
            expires_at?: string | null;
            /** Id */
            id: number;
            /** Last Seen At */
            last_seen_at?: string | null;
            /** User Id */
            user_id?: number | null;
        };
        /** SessionUpdateRequest */
        SessionUpdateRequest: {
            /** Ended At */
            ended_at?: string | null;
            /** Expires At */
            expires_at?: string | null;
            /** Last Seen At */
            last_seen_at?: string | null;
        };
        /** SimulationCreateRequest */
        SimulationCreateRequest: {
            /** Coach Prompt Id */
            coach_prompt_id?: number | null;
            /** Corpus Id */
            corpus_id: number;
            /** Corpus Index Id */
            corpus_index_id: number;
            /** Counter Part Side Persona Id */
            counter_part_side_persona_id?: number | null;
            /** Counterpart Prompt Id */
            counterpart_prompt_id?: number | null;
            /** Description */
            description?: string | null;
            /** Evaluator Prompt Id */
            evaluator_prompt_id?: number | null;
            /** Simulation name */
            name: string;
            /** Scenario Id */
            scenario_id?: number | null;
            /** Session Id */
            session_id?: number | null;
            /** User Id Participant */
            user_id_participant?: number | null;
            /** User Side */
            user_side?: ("side_a" | "side_b") | null;
        };
        /** SimulationEvaluationListItem */
        SimulationEvaluationListItem: {
            /** Coach Prompt Id */
            coach_prompt_id?: number | null;
            /** Corpus Id */
            corpus_id: number;
            /** Corpus Index Id */
            corpus_index_id: number;
            /** Counter Part Side Persona Id */
            counter_part_side_persona_id?: number | null;
            /** Counterpart Prompt Id */
            counterpart_prompt_id?: number | null;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Description */
            description?: string | null;
            /** Evaluator Prompt Id */
            evaluator_prompt_id?: number | null;
            /** Id */
            id: number;
            /**
             * Last Updated
             * Format: date-time
             */
            last_updated: string;
            /** Simulation name */
            name: string;
            /** Participant User Id */
            participant_user_id: number;
            /** Reviewed At */
            reviewed_at?: string | null;
            /** Scenario Id */
            scenario_id?: number | null;
            /** Scenario Name */
            scenario_name?: string | null;
            /** Session Id */
            session_id?: number | null;
            /** Status */
            status: string;
            /** Teacher Feedback */
            teacher_feedback?: string | null;
            /** Teacher Id */
            teacher_id?: number | null;
            /** Teacher Reviewed */
            teacher_reviewed: boolean;
            /** User Id Owner */
            user_id_owner: number;
            /** User Id Participant */
            user_id_participant?: number | null;
            /** User Side */
            user_side?: string | null;
        };
        /** SimulationEvaluationListResponse */
        SimulationEvaluationListResponse: {
            /**
             * Has More
             * @default false
             */
            has_more: boolean;
            /** Items */
            items?: components["schemas"]["SimulationEvaluationListItem"][];
            /**
             * Limit
             * @default 20
             */
            limit: number;
            /**
             * Skip
             * @default 0
             */
            skip: number;
        };
        /** SimulationMessageSchema */
        SimulationMessageSchema: {
            /** Content */
            content: string;
            /** Metadata */
            metadata?: {
                [key: string]: unknown;
            };
            /** Role */
            role: string;
            /** Timestamp */
            timestamp?: string | null;
        };
        /** SimulationProxyDisableResponse */
        SimulationProxyDisableResponse: {
            /**
             * Auto User Proxy Enabled
             * @default false
             */
            auto_user_proxy_enabled: boolean;
            /** Messages */
            messages?: components["schemas"]["SimulationMessageSchema"][];
            /** Simulation Id */
            simulation_id: number;
            /**
             * Status
             * @enum {string}
             */
            status: "created" | "active" | "paused" | "completed" | "cancelled" | "failed";
            /** User Proxy Persona */
            user_proxy_persona?: {
                [key: string]: unknown;
            };
        };
        /** SimulationProxyTurnRequest */
        SimulationProxyTurnRequest: {
            /**
             * Duration
             * @enum {string}
             */
            duration: "this_turn" | "remainder";
            /** Persona Id */
            persona_id?: number | null;
        };
        /** SimulationProxyTurnResponse */
        SimulationProxyTurnResponse: {
            /**
             * Auto User Proxy Enabled
             * @default false
             */
            auto_user_proxy_enabled: boolean;
            /** Coach Advice */
            coach_advice?: {
                [key: string]: unknown;
            };
            /** Counterpart Response */
            counterpart_response?: string | null;
            /** Final Evaluation */
            final_evaluation?: {
                [key: string]: unknown;
            };
            /** Messages */
            messages?: components["schemas"]["SimulationMessageSchema"][];
            /** Pause Reason */
            pause_reason?: string | null;
            /** Phase */
            phase?: string | null;
            /** Proxy Response */
            proxy_response: string;
            /**
             * Should Pause
             * @default false
             */
            should_pause: boolean;
            /** Simulation Id */
            simulation_id: number;
            /**
             * Status
             * @enum {string}
             */
            status: "created" | "active" | "paused" | "completed" | "cancelled" | "failed";
            /** User Proxy Persona */
            user_proxy_persona?: {
                [key: string]: unknown;
            };
        };
        /** SimulationRead */
        SimulationRead: {
            /** Coach Prompt Id */
            coach_prompt_id?: number | null;
            /** Corpus Id */
            corpus_id: number;
            /** Corpus Index Id */
            corpus_index_id: number;
            /** Counter Part Side Persona Id */
            counter_part_side_persona_id?: number | null;
            /** Counterpart Prompt Id */
            counterpart_prompt_id?: number | null;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Description */
            description?: string | null;
            /** Evaluator Prompt Id */
            evaluator_prompt_id?: number | null;
            /** Id */
            id: number;
            /**
             * Last Updated
             * Format: date-time
             */
            last_updated: string;
            /** Simulation name */
            name: string;
            /** Reviewed At */
            reviewed_at?: string | null;
            /** Scenario Id */
            scenario_id?: number | null;
            /** Session Id */
            session_id?: number | null;
            /** Status */
            status: string;
            /** Teacher Feedback */
            teacher_feedback?: string | null;
            /** Teacher Id */
            teacher_id?: number | null;
            /** Teacher Reviewed */
            teacher_reviewed: boolean;
            /** User Id Owner */
            user_id_owner: number;
            /** User Id Participant */
            user_id_participant?: number | null;
            /** User Side */
            user_side?: string | null;
        };
        /** SimulationReadWithState */
        SimulationReadWithState: {
            /** Coach Prompt Id */
            coach_prompt_id?: number | null;
            /** Corpus Id */
            corpus_id: number;
            /** Corpus Index Id */
            corpus_index_id: number;
            /** Counter Part Side Persona Id */
            counter_part_side_persona_id?: number | null;
            /** Counterpart Prompt Id */
            counterpart_prompt_id?: number | null;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Description */
            description?: string | null;
            /** Evaluator Prompt Id */
            evaluator_prompt_id?: number | null;
            /** Id */
            id: number;
            /**
             * Last Updated
             * Format: date-time
             */
            last_updated: string;
            /** Messages */
            messages?: components["schemas"]["SimulationMessageSchema"][];
            /** Simulation name */
            name: string;
            negotiation_state?: components["schemas"]["NegotiationStateSchema"];
            /** Reviewed At */
            reviewed_at?: string | null;
            /** Scenario Id */
            scenario_id?: number | null;
            /** Session Id */
            session_id?: number | null;
            /** Status */
            status: string;
            /** Teacher Feedback */
            teacher_feedback?: string | null;
            /** Teacher Id */
            teacher_id?: number | null;
            /** Teacher Reviewed */
            teacher_reviewed: boolean;
            /** User Id Owner */
            user_id_owner: number;
            /** User Id Participant */
            user_id_participant?: number | null;
            /** User Side */
            user_side?: string | null;
        };
        /** SimulationStartRequest */
        SimulationStartRequest: {
            /**
             * Max Turn Count
             * @default 12
             */
            max_turn_count: number;
            /** Side A */
            side_a?: {
                [key: string]: unknown;
            };
            /** Side B */
            side_b?: {
                [key: string]: unknown;
            };
        };
        /** SimulationTeacherReviewRequest */
        SimulationTeacherReviewRequest: {
            /** Teacher Feedback */
            teacher_feedback: string;
        };
        /** SimulationTurnRequest */
        SimulationTurnRequest: {
            /** Action */
            action?: ("continue" | "end") | null;
            /** Current Offer */
            current_offer?: {
                [key: string]: unknown;
            } | null;
            /** Message */
            message: string;
        };
        /** SimulationTurnResponse */
        SimulationTurnResponse: {
            /** Coach Advice */
            coach_advice?: {
                [key: string]: unknown;
            };
            /** Counterpart Response */
            counterpart_response?: string | null;
            /** Final Evaluation */
            final_evaluation?: {
                [key: string]: unknown;
            };
            /** Messages */
            messages?: components["schemas"]["SimulationMessageSchema"][];
            /** Pause Reason */
            pause_reason?: string | null;
            /** Phase */
            phase?: string | null;
            /**
             * Should Pause
             * @default false
             */
            should_pause: boolean;
            /** Simulation Id */
            simulation_id: number;
            /**
             * Status
             * @enum {string}
             */
            status: "created" | "active" | "paused" | "completed" | "cancelled" | "failed";
        };
        /** SimulationUpdateRequest */
        SimulationUpdateRequest: {
            /** Coach Prompt Id */
            coach_prompt_id?: number | null;
            /** Corpus Index Id */
            corpus_index_id?: number | null;
            /** Counter Part Side Persona Id */
            counter_part_side_persona_id?: number | null;
            /** Counterpart Prompt Id */
            counterpart_prompt_id?: number | null;
            /** Description */
            description?: string | null;
            /** Evaluator Prompt Id */
            evaluator_prompt_id?: number | null;
            /** Simulation name */
            name?: string | null;
            /** Scenario Id */
            scenario_id?: number | null;
            /** Session Id */
            session_id?: number | null;
            /** Status */
            status?: ("created" | "active" | "paused" | "completed" | "cancelled" | "failed") | null;
            /** User Id Participant */
            user_id_participant?: number | null;
            /** User Side */
            user_side?: ("side_a" | "side_b") | null;
        };
        /** Token */
        Token: {
            /** Access Token */
            access_token: string;
            /** Expires At */
            expires_at?: string | null;
            /** Session Id */
            session_id?: number | null;
            /**
             * Token Type
             * @default bearer
             */
            token_type: string;
        };
        /** UserCreate */
        UserCreate: {
            /** Password */
            password: string;
            /** Role IDs */
            role_ids: number[];
            /** Username */
            username: string;
        };
        /** UserCreatedResponse */
        UserCreatedResponse: {
            /**
             * Ok
             * @default true
             */
            ok: boolean;
            user: components["schemas"]["UserRead"];
        };
        /** UserPasswordChange */
        UserPasswordChange: {
            /** Current password */
            current_password: string;
            /** New password */
            new_password: string;
        };
        /** UserRead */
        UserRead: {
            /** Id */
            id: number;
            /** Roles */
            roles?: components["schemas"]["RoleRead"][];
            /** Username */
            username: string;
        };
        /** UserUpdate */
        UserUpdate: {
            /** Password */
            password?: string | null;
            /** Role IDs */
            role_ids?: number[] | null;
            /** Username */
            username?: string | null;
        };
        /** ValidationError */
        ValidationError: {
            /** Context */
            ctx?: Record<string, never>;
            /** Input */
            input?: unknown;
            /** Location */
            loc: (string | number)[];
            /** Message */
            msg: string;
            /** Error Type */
            type: string;
        };
        /** VectorStoreConnectionUpdate */
        VectorStoreConnectionUpdate: {
            /** Collection Name */
            collection_name?: string | null;
            /** Connection Uri */
            connection_uri?: string | null;
            /** Path */
            path?: string | null;
            /** Store Metadata */
            store_metadata?: {
                [key: string]: unknown;
            } | null;
            /** Table Name */
            table_name?: string | null;
        };
        /** VectorStoreCreate */
        VectorStoreCreate: {
            /**
             * Vector store backend
             * @enum {string}
             */
            backend: "chroma" | "faiss" | "pgvector";
            /** Collection Name */
            collection_name?: string | null;
            /** Connection Uri */
            connection_uri?: string | null;
            /** Embedding model */
            embedding_model: string;
            /** Vector store name */
            name: string;
            /** Path */
            path?: string | null;
            /** Store Metadata */
            store_metadata?: {
                [key: string]: unknown;
            };
            /** Table Name */
            table_name?: string | null;
        };
        /** VectorStoreReadWithIds */
        VectorStoreReadWithIds: {
            /**
             * Vector store backend
             * @enum {string}
             */
            backend: "chroma" | "faiss" | "pgvector";
            /** Collection Name */
            collection_name?: string | null;
            /** Connection Uri */
            connection_uri?: string | null;
            /** Corpus Index Ids */
            corpus_index_ids?: number[];
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Embedding Dimensions */
            embedding_dimensions?: number | null;
            /** Id */
            id: number;
            /**
             * Last Updated
             * Format: date-time
             */
            last_updated: string;
            /** Vector store name */
            name: string;
            /** Path */
            path?: string | null;
            /** Store Metadata */
            store_metadata?: {
                [key: string]: unknown;
            };
            /** Table Name */
            table_name?: string | null;
        };
        /** VectorStoreUpdate */
        VectorStoreUpdate: {
            /** Backend */
            backend?: ("chroma" | "faiss" | "pgvector") | null;
            /** Collection Name */
            collection_name?: string | null;
            /** Connection Uri */
            connection_uri?: string | null;
            /** Vector store name */
            name?: string | null;
            /** Path */
            path?: string | null;
            /** Store Metadata */
            store_metadata?: {
                [key: string]: unknown;
            } | null;
            /** Table Name */
            table_name?: string | null;
        };
    };
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
};
export type $defs = Record<string, never>;
export interface operations {
    list_chunking_profiles_chunking_profiles__get: {
        parameters: {
            query?: {
                has_references?: boolean | null;
                limit?: number;
                name_contains?: string | null;
                skip?: number;
                strategy?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ChunkingProfileReadWithIds"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_chunking_profile_chunking_profiles__post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ChunkingProfileCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ChunkingProfileReadWithIds"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_chunking_profile_chunking_profiles__profile_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                profile_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ChunkingProfileReadWithIds"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_chunking_profile_chunking_profiles__profile_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                profile_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_chunking_profile_chunking_profiles__profile_id__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                profile_id: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ChunkingProfileUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ChunkingProfileReadWithIds"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    copy_chunking_profile_chunking_profiles__profile_id__copy_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                profile_id: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ChunkingProfileCopy"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ChunkingProfileReadWithIds"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_chunker_definitions_chunking_profiles_definitions_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ChunkerDefinitionRead"][];
                };
            };
        };
    };
    list_corpora_corpora__get: {
        parameters: {
            query?: {
                created_by_user_id?: number | null;
                has_indices?: boolean | null;
                limit?: number;
                raw_document_id?: number | null;
                skip?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CorpusRead"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_corpus_corpora__post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CorpusCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CorpusRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    chunk_corpus_corpora__corpus_id__chunking_profiles__profile_id__chunk_post: {
        parameters: {
            query?: {
                preview?: boolean;
            };
            header?: never;
            path: {
                corpus_id: number;
                profile_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CorpusChunkResult"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    ingest_corpus_corpora__corpus_id__chunking_profiles__profile_id__ingest_post: {
        parameters: {
            query?: {
                dynamic_header_depth?: boolean;
                header_depth?: number;
            };
            header?: never;
            path: {
                corpus_id: number;
                profile_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CorpusIngestResult"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    embed_corpus_corpora__corpus_id__chunking_profiles__profile_id__vector_stores__vector_store_id__embed_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                corpus_id: number;
                profile_id: number;
                vector_store_id: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CorpusEmbeddingBuildRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CorpusEmbeddingBuildResult"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    queue_embed_corpus_job_corpora__corpus_id__chunking_profiles__profile_id__vector_stores__vector_store_id__embed_jobs_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                corpus_id: number;
                profile_id: number;
                vector_store_id: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CorpusEmbeddingBuildRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CorpusEmbeddingBuildQueued"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_corpus_indices_corpus_indices__get: {
        parameters: {
            query?: {
                chunking_profile_id?: number | null;
                corpus_id?: number | null;
                has_indexed_chunks?: boolean | null;
                limit?: number;
                skip?: number;
                status?: string | null;
                vector_store_id?: number | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CorpusIndexReadWithIds"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_corpus_index_corpus_indices__post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CorpusIndexCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CorpusIndexReadWithIds"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_corpus_index_corpus_indices__index_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                index_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CorpusIndexReadWithIds"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_corpus_index_corpus_indices__index_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                index_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_corpus_index_corpus_indices__index_id__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                index_id: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CorpusIndexMetadataUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CorpusIndexReadWithIds"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    mark_corpus_index_built_corpus_indices__index_id__build_complete_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                index_id: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CorpusIndexBuildComplete"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CorpusIndexReadWithIds"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    copy_corpus_index_corpus_indices__index_id__copy_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                index_id: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CorpusIndexCopy"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CorpusIndexReadWithIds"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_corpus_index_indexed_chunks_corpus_indices__index_id__indexed_chunks_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                index_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CorpusIndexReadWithIndexedChunks"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_corpus_index_status_corpus_indices__index_id__status_patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                index_id: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CorpusIndexStatusUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CorpusIndexReadWithIds"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_counterpart_personas_counterpart_personas__get: {
        parameters: {
            query?: {
                created_by_user_id?: number | null;
                limit?: number;
                name_contains?: string | null;
                skip?: number;
                used?: boolean | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CounterpartPersonaReadWithIds"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_counterpart_persona_counterpart_personas__post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CounterpartPersonaCreateRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CounterpartPersonaReadWithIds"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_counterpart_persona_counterpart_personas__persona_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                persona_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CounterpartPersonaReadWithIds"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_counterpart_persona_counterpart_personas__persona_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                persona_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_counterpart_persona_counterpart_personas__persona_id__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                persona_id: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CounterpartPersonaUpdateRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CounterpartPersonaReadWithIds"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    copy_counterpart_persona_counterpart_personas__persona_id__copy_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                persona_id: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CounterpartPersonaCopyRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CounterpartPersonaReadWithIds"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_embedding_models_embeddings_models_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["EmbeddingModelRead"][];
                };
            };
        };
    };
    list_indexing_jobs_indexing_jobs__get: {
        parameters: {
            query?: {
                corpus_id?: number | null;
                limit?: number;
                skip?: number;
                status_filter?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["IndexingJobQueued"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_indexing_job_indexing_jobs__post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["IndexingJobCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["IndexingJobQueued"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_indexing_job_detail_indexing_jobs__job_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                job_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["IndexingJobDetail"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    cancel_indexing_job_indexing_jobs__job_id__cancel_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                job_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["IndexingJobDetail"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_active_indexing_job_indexing_jobs_active_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["IndexingJobDetail"];
                };
            };
        };
    };
    list_prompts_prompts__get: {
        parameters: {
            query?: {
                is_system?: boolean | null;
                limit?: number;
                name_contains?: string | null;
                owner_id?: number | null;
                skip?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PromptRead"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_prompt_prompts__post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PromptCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PromptRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_prompt_prompts__prompt_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                prompt_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PromptRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_prompt_prompts__prompt_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                prompt_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_prompt_prompts__prompt_id__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                prompt_id: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PromptAdminUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PromptRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    copy_prompt_prompts__prompt_id__copy_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                prompt_id: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PromptClone"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PromptRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_raw_documents_raw_documents__get: {
        parameters: {
            query?: {
                corpus_id?: number | null;
                limit?: number;
                name_contains?: string | null;
                skip?: number;
                uploaded_by_user_id?: number | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RawDocumentRead"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_raw_document_raw_documents__post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "multipart/form-data": components["schemas"]["Body_create_raw_document_raw_documents__post"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RawDocumentRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_raw_document_by_id_raw_documents__raw_document_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                raw_document_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RawDocumentRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    chunk_raw_document_raw_documents__raw_document_id__chunking_profiles__profile_id__chunk_post: {
        parameters: {
            query?: {
                preview?: boolean;
            };
            header?: never;
            path: {
                profile_id: number;
                raw_document_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RawDocumentChunkResult"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    ingest_raw_document_raw_documents__raw_document_id__chunking_profiles__profile_id__ingest_post: {
        parameters: {
            query?: {
                dynamic_header_depth?: boolean;
                header_depth?: number;
            };
            header?: never;
            path: {
                profile_id: number;
                raw_document_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RawDocumentIngestResult"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_scenarios_scenarios__get: {
        parameters: {
            query?: {
                created_by_user_id?: number | null;
                limit?: number;
                name_contains?: string | null;
                skip?: number;
                used?: boolean | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ScenarioPublicReadWithIds"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_scenario_scenarios__post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ScenarioCreateRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ScenarioAuthoringReadWithIds"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_scenario_scenarios__scenario_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                scenario_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ScenarioPublicReadWithIds"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_scenario_scenarios__scenario_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                scenario_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_scenario_scenarios__scenario_id__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                scenario_id: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ScenarioUpdateRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ScenarioAuthoringReadWithIds"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_scenario_authoring_scenarios__scenario_id__authoring_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                scenario_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ScenarioAuthoringReadWithIds"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    copy_scenario_scenarios__scenario_id__copy_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                scenario_id: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ScenarioCopyRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ScenarioAuthoringReadWithIds"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    generate_scenario_context_scenarios_generate_context_post: {
        parameters: {
            query?: {
                model_name?: string;
                provider?: string;
                temperature?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ScenarioContextGenerateRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ScenarioContextGenerateResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_sessions_sessions__get: {
        parameters: {
            query?: {
                active?: boolean | null;
                expired?: boolean | null;
                limit?: number;
                skip?: number;
                user_id?: number | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SessionRead"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_session_sessions__post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SessionCreateRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SessionRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_session_sessions__session_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                session_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SessionRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_session_sessions__session_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                session_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_session_sessions__session_id__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                session_id: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SessionUpdateRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SessionRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    end_session_sessions__session_id__end_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                session_id: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SessionEnd"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SessionRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    heartbeat_session_sessions__session_id__heartbeat_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                session_id: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SessionHeartbeat"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SessionRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_simulations_simulations__get: {
        parameters: {
            query?: {
                coach_prompt_id?: number | null;
                corpus_id?: number | null;
                corpus_index_id?: number | null;
                counterpart_prompt_id?: number | null;
                evaluator_prompt_id?: number | null;
                limit?: number;
                owner_id?: number | null;
                participant_id?: number | null;
                scenario_id?: number | null;
                session_id?: number | null;
                skip?: number;
                status?: ("created" | "active" | "paused" | "completed" | "cancelled" | "failed") | null;
                teacher_id?: number | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SimulationRead"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_simulation_simulations__post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SimulationCreateRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SimulationRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_simulation_simulations__simulation_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                simulation_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SimulationReadWithState"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_simulation_simulations__simulation_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                simulation_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_simulation_simulations__simulation_id__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                simulation_id: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SimulationUpdateRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SimulationRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    cancel_simulation_simulations__simulation_id__cancel_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                simulation_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SimulationRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    submit_simulation_proxy_turn_simulations__simulation_id__proxy_turn_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                simulation_id: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SimulationProxyTurnRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SimulationProxyTurnResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    disable_simulation_proxy_simulations__simulation_id__proxy_disable_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                simulation_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SimulationProxyDisableResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    review_simulation_simulations__simulation_id__review_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                simulation_id: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SimulationTeacherReviewRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SimulationRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_review_simulation_simulations__simulation_id__review_delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                simulation_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_review_simulation_simulations__simulation_id__review_patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                simulation_id: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SimulationTeacherReviewRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SimulationRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    start_simulation_simulations__simulation_id__start_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                simulation_id: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SimulationStartRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SimulationReadWithState"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_simulation_state_simulations__simulation_id__state_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                simulation_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SimulationReadWithState"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    submit_simulation_turn_simulations__simulation_id__turn_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                simulation_id: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SimulationTurnRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SimulationTurnResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_completed_simulations_simulations_completed_get: {
        parameters: {
            query?: {
                limit?: number;
                skip?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SimulationEvaluationListResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_reviewed_simulations_simulations_reviews_get: {
        parameters: {
            query?: {
                limit?: number;
                skip?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SimulationEvaluationListResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_all_users_users__get: {
        parameters: {
            query?: {
                limit?: number;
                skip?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["UserRead"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_user_users__user_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                user_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_user_users__user_id__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                user_id: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["UserUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["UserRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_user_by_username_users__username__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                username: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["UserRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    login_users_login_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/x-www-form-urlencoded": components["schemas"]["Body_login_users_login_post"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Token"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_me_user_users_me_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["UserRead"];
                };
            };
        };
    };
    change_own_password_users_me_password_patch: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["UserPasswordChange"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["UserRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_user_users_register_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["UserCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["UserCreatedResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_roles_users_roles_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RoleRead"][];
                };
            };
        };
    };
    list_vector_stores_vector_stores__get: {
        parameters: {
            query?: {
                backend?: ("chroma" | "faiss" | "pgvector") | null;
                has_indexes?: boolean | null;
                limit?: number;
                skip?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["VectorStoreReadWithIds"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_vector_store_vector_stores__post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["VectorStoreCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["VectorStoreReadWithIds"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_vector_store_vector_stores__vector_store_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                vector_store_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["VectorStoreReadWithIds"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_vector_store_vector_stores__vector_store_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                vector_store_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_vector_store_vector_stores__vector_store_id__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                vector_store_id: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["VectorStoreUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["VectorStoreReadWithIds"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_vector_store_connection_vector_stores__vector_store_id__connection_patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                vector_store_id: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["VectorStoreConnectionUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["VectorStoreReadWithIds"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
}

