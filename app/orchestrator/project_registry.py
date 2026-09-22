from app.database import get_connection

from .project import Project


class ProjectRegistry:
    def __init__(self):
        self._projects: dict[str, Project] = {}
        self.load_from_database()

    def register(self, project: Project) -> None:
        if project.id in self._projects:
            raise ValueError(
                f"Project already registered: {project.id}"
            )

        self._projects[project.id] = project
        self.save_to_database(project)

    def get(self, project_id: str) -> Project:
        try:
            return self._projects[project_id]
        except KeyError:
            raise ValueError(
                f"Project not found: {project_id}"
            )

    def all(self) -> list[Project]:
        return list(self._projects.values())

    def exists(self, project_id: str) -> bool:
        return project_id in self._projects

    def save_to_database(self, project: Project) -> None:
        connection = get_connection()

        try:
            connection.execute(
                """
                INSERT INTO projects (
                    id,
                    name,
                    description,
                    status
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    project.id,
                    project.name,
                    project.description,
                    project.status,
                ),
            )

            connection.commit()

        finally:
            connection.close()

    def load_from_database(self) -> None:
        connection = get_connection()

        try:
            rows = connection.execute(
                """
                SELECT
                    id,
                    name,
                    description,
                    status
                FROM projects
                ORDER BY created_at ASC
                """
            ).fetchall()

            for row in rows:
                project = Project(
                    id=row["id"],
                    name=row["name"],
                    description=row["description"],
                    status=row["status"],
                )

                self._projects[project.id] = project

        finally:
            connection.close()