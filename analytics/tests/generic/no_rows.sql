{% test no_rows(model) %}
select * from {{ model }}
{% endtest %}
