{% macro test_rank_score_range(model, column_name='rank_score') %}
    {# 
    Test that rank_score is within valid range (0-100).
    
    Args:
        model: The model to test
        column_name: Column name for rank score (default: rank_score)
    #}
    
    select *
    from {{ model }}
    where 
        {{ column_name }} < 0 
        or {{ column_name }} > 100
    
{% endmacro %}

