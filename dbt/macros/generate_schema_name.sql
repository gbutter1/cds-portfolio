{#
  By default dbt names custom schemas "<target schema>_<custom schema>",
  which would give us analytics_staging / analytics_marts. We want plain
  staging / marts, so the custom name wins when one is set.
#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
