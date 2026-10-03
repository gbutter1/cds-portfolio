{# Format a numeric expression as dollars for human-readable exception text, e.g. $1,234.50 #}
{% macro rr_money(expr) -%}
to_char({{ expr }}, 'FM$999,999,990.00')
{%- endmacro %}
