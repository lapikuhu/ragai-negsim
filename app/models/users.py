### ----------------------------- USERS MODELS------------------------- ###
# Models define the database structure and are used for ORM operations. 
# They are only called by repositories and services, not directly by routes.

from sqlmodel import Field, Relationship, SQLModel
from typing import TYPE_CHECKING
from .user_roles import UserRoleLink

if TYPE_CHECKING: # Avoid circular imports by only importing Role for type checking
    from .user_roles import Role
    from .simulations import Simulation
    from .sessions import Session
    from .prompts import Prompt
    from .raw_documents import RawDocument
    from .corpus import Corpus
    from .scenarios import Scenario
    from .counterpart_personas import CounterPartPersonas

class User(SQLModel, table=True):
    id : int | None = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True, title="Username", min_length=3)
    hashed_password: str = Field(index=True, title="Hashed Password")
    roles: list["Role"] = Relationship(back_populates="users", link_model=UserRoleLink)
    prompts: list["Prompt"] = Relationship(back_populates="owner")
    simulations_participated: list["Simulation"] = Relationship(
        back_populates="participant",
        sa_relationship_kwargs={"foreign_keys": "[Simulation.user_id_participant]"},
) # the simulations the user has participated in (as participant)
    simulations_owned: list["Simulation"] = Relationship(
        back_populates="owner",
        sa_relationship_kwargs={"foreign_keys": "[Simulation.user_id_owner]"},
) # The simulations the user owns (created)
    simulations_reviewed: list["Simulation"] = Relationship(
        back_populates="teacher",
        sa_relationship_kwargs={"foreign_keys": "[Simulation.teacher_id]"},
) # The simulations the teacher has reviewed
    sessions: list["Session"] = Relationship(
        back_populates ="user",
        sa_relationship_kwargs={"foreign_keys": "[Session.user_id]"},
) # The sessions the user has participated in (logged in)
    raw_documents_uploaded: list["RawDocument"] = Relationship(back_populates="uploaded_by")
    corpora_created: list["Corpus"] = Relationship(
        back_populates="created_by_user",
        sa_relationship_kwargs={"foreign_keys": "[Corpus.created_by_user_id]"},
    )
    corpora_last_edited: list["Corpus"] = Relationship(
        back_populates="last_edit_by_user",
        sa_relationship_kwargs={"foreign_keys": "[Corpus.last_edit_by_user_id]"},
    )
    scenarios_created: list["Scenario"] = Relationship(
        back_populates="created_by_user",
        sa_relationship_kwargs={"foreign_keys": "[Scenario.created_by_user_id]"},
    )
    scenarios_last_edited: list["Scenario"] = Relationship(
        back_populates="last_edit_by_user",
        sa_relationship_kwargs={"foreign_keys": "[Scenario.last_edit_by_user_id]"},
    )
    counterpart_personas_created: list["CounterPartPersonas"] = Relationship(
        back_populates="created_by_user",
        sa_relationship_kwargs={"foreign_keys": "[CounterPartPersonas.created_by_user_id]"},
    )
    counterpart_personas_last_edited: list["CounterPartPersonas"] = Relationship(
        back_populates="last_edit_by_user",
        sa_relationship_kwargs={"foreign_keys": "[CounterPartPersonas.last_edit_by_user_id]"},
    )