{% macro test_composite_relationship(model, column_name, to, field, composite_fields) %}
  {#-
    Test that a composite foreign key relationship exists in the parent table.
    
    Args:
        model: The child model (e.g., ref('dim_ranking'))
        column_name: The column name being tested (automatically passed by dbt for column-level tests)
        to: The parent model (e.g., ref('fact_jobs'))
        field: The primary field name (e.g., 'jsearch_job_id')
        composite_fields: List of field names that form the composite key (e.g., ['jsearch_job_id', 'campaign_id'])
    
    Example:
        composite_relationship:
          to: ref('fact_jobs')
          field: jsearch_job_id
          composite_fields:
            - jsearch_job_id
            - campaign_id
  -#}

  {%- set fields = composite_fields -%}
  {%- set field_list = fields | join(', ') -%}
  {%- set conditions = [] -%}
  
  {%- for field_name in fields -%}
    {%- set condition = "child." ~ field_name ~ " = parent." ~ field_name -%}
    {%- set _ = conditions.append(condition) -%}
  {%- endfor -%}
  
  {%- set join_condition = conditions | join(' AND ') -%}

  with child as (
    select {{ field_list }}
    from {{ model }}
    where {{ field }} is not null
  ),

  parent as (
    select {{ field_list }}
    from {{ to }}
  )

  select
    child.*
  from child
  left join parent
    on {{ join_condition }}
  where parent.{{ field }} is null

{% endmacro %}

