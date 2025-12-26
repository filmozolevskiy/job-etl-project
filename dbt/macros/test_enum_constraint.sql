{% macro test_enum_constraint(model, column_name, allowed_values) %}
    {# 
    Test that column values are within allowed set (enum constraint).
    
    Args:
        model: The model to test
        column_name: Column name to test
        allowed_values: List of allowed values (e.g., ['pending', 'success', 'error'])
    #}
    
    select *
    from {{ model }}
    where 
        {{ column_name }} is not null
        and {{ column_name }} not in (
            {% for value in allowed_values %}
                '{{ value }}'{% if not loop.last %},{% endif %}
            {% endfor %}
        )
    
{% endmacro %}

