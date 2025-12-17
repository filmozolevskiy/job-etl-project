-- Custom test macro to check unique combination of columns

{% test assert_unique_combination(model, combination_of_columns) %}

  {%- set columns_csv = combination_of_columns | join(', ') -%}

  with validation as (
    select
      {{ columns_csv }},
      count(*) as count
    from {{ model }}
    group by {{ columns_csv }}
    having count(*) > 1
  )

  select *
  from validation

{% endtest %}

