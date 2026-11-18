{% test price_within_tolerance(model, column_name, golden_column, tolerance_pct=1) %}
-- Returns the rows whose channel price is further than tolerance_pct from the golden price.
select *
from {{ model }}
where abs({{ column_name }} - {{ golden_column }}) > {{ golden_column }} * {{ tolerance_pct }} / 100.0
{% endtest %}
