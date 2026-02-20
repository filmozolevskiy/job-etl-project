"""
Integration tests for DAG task order verification.

Tests that the DAG task dependencies ensure correct execution order,
specifically that fact_jobs is built before rankings are created.
"""

import pytest

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


class TestDAGTaskOrder:
    """Test DAG task order to prevent orphaned rankings."""

    def test_dag_task_order_ensures_fact_jobs_before_ranking(self):
        """
        Test that DAG task dependencies ensure fact_jobs is built before ranking.

        This test verifies the DAG structure:
        - normalize_jobs → dbt_modelling → rank_jobs
        - This ensures fact_jobs is populated before rank_jobs runs
        """
        try:
            from airflow.dags.jobs_etl_daily import dag
        except ImportError:
            pytest.skip("Airflow is not installed. Install Airflow to run DAG structure tests.")

        # Get task IDs
        normalize_jobs_task = dag.get_task("normalize_jobs")
        dbt_modelling_task = dag.get_task("dbt_modelling")
        rank_jobs_task = dag.get_task("rank_jobs")

        # Verify tasks exist
        assert normalize_jobs_task is not None, "normalize_jobs task should exist"
        assert dbt_modelling_task is not None, "dbt_modelling task should exist"
        assert rank_jobs_task is not None, "rank_jobs task should exist"

        # Verify task dependencies using topological sort
        # Get all upstream tasks for rank_jobs
        upstream_tasks = rank_jobs_task.upstream_task_ids

        # rank_jobs should depend on dbt_modelling
        assert (
            "dbt_modelling" in upstream_tasks
        ), "rank_jobs should depend on dbt_modelling to ensure fact_jobs is built before ranking"

        # Get all upstream tasks for dbt_modelling
        dbt_upstream = dbt_modelling_task.upstream_task_ids

        # dbt_modelling should depend on normalize_jobs (directly or indirectly)
        # It may also depend on normalize_companies and enricher, but normalize_jobs
        # should be in the dependency chain
        all_dbt_upstream = set()
        for task_id in dbt_upstream:
            all_dbt_upstream.add(task_id)
            # Get transitive upstream tasks
            task = dag.get_task(task_id)
            all_dbt_upstream.update(task.upstream_task_ids)

        assert "normalize_jobs" in all_dbt_upstream, (
            "dbt_modelling should depend on normalize_jobs (directly or indirectly) "
            "to ensure jobs are normalized before building fact_jobs"
        )

        # Verify the complete chain: normalize_jobs → dbt_modelling → rank_jobs
        # This ensures fact_jobs is populated before ranking
        assert (
            "normalize_jobs" in all_dbt_upstream
        ), "normalize_jobs must be upstream of dbt_modelling"
        assert "dbt_modelling" in upstream_tasks, "dbt_modelling must be upstream of rank_jobs"

    def test_dag_topological_sort_places_rank_jobs_after_dbt_modelling(self):
        """
        Test that topological sort places rank_jobs after dbt_modelling.

        This ensures that when the DAG runs, dbt_modelling completes
        before rank_jobs starts, preventing orphaned rankings.
        """
        try:
            from airflow.dags.jobs_etl_daily import dag
        except ImportError:
            pytest.skip("Airflow is not installed. Install Airflow to run DAG structure tests.")

        # Get topological sort of tasks
        task_order = dag.topological_sort()

        # Find positions of key tasks
        dbt_modelling_pos = None
        rank_jobs_pos = None

        for i, task_id in enumerate(task_order):
            if task_id == "dbt_modelling":
                dbt_modelling_pos = i
            elif task_id == "rank_jobs":
                rank_jobs_pos = i

        # Verify both tasks are in the order
        assert dbt_modelling_pos is not None, "dbt_modelling should be in task order"
        assert rank_jobs_pos is not None, "rank_jobs should be in task order"

        # Verify dbt_modelling comes before rank_jobs
        assert dbt_modelling_pos < rank_jobs_pos, (
            f"dbt_modelling (position {dbt_modelling_pos}) should come before "
            f"rank_jobs (position {rank_jobs_pos}) in topological sort. "
            "This ensures fact_jobs is built before rankings are created."
        )
