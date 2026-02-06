💰 Revenue & performance
- "What are the top 10 customers by revenue?"
- "Total revenue last month"
- "Revenue by store for the last 6 months"
- "Top 5 stores by revenue this year"
- "Revenue by film category in Q4"
- "Average revenue per customer by country"
- "Which films generate the most revenue per rental?"
- "Revenue from repeat customers vs new customers"
- "Share of total revenue by store"

🔍 Tests: measures, grouping, time filters, joins through multiple tables

⸻

📦 Products / content (films)
- "Top 10 films by revenue"
- "Most rented films last quarter"
- "Which categories perform best by revenue?"
- "Average rental duration per film category"
- "Films that are rented often but generate little revenue"
- "Revenue per inventory item"
- "Which actors appear in the highest-grossing films?"

🔍 Tests: many-to-many joins, popularity vs revenue, semantic paths

⸻

👥 Customers & behavior
- "Number of active customers by country"
- "Customers with more than 10 rentals"
- "Average revenue per customer"
- "Top 10 customers by lifetime value"
- "Customers who haven’t rented anything in the last 90 days"
- "Repeat customers vs one-time customers"
- "Customer retention by signup month"

🔍 Tests: cohort logic, churn definitions, lifetime metrics

⸻

⏱ Time & trends
- "Revenue by month for the last year"
- "Compare this month to the same month last year"
- "Week-over-week rental growth"
- "Seasonality of rentals by category"
- "Best performing month historically"
- "Trend of average rental duration over time"

🔍 Tests: time intelligence, date truncation, comparisons

⸻

🏪 Stores & staff
- "Revenue by store"
- "Revenue per staff member"
- "Which store is growing fastest?"
- "Average transaction value per store"
- "Staff members handling the most rentals"
- "Store performance before and after last year"

🔍 Tests: attribution, hierarchical grouping, joins across dimensions

⸻

🎯 Operational / edge-case questions (great for LLMs)
- "Which customers rent often but spend little?"
- "Which films are rarely rented but generate high revenue?"
- "Customers who rented last month but not this month". Follow up question "compare that month over month for the last 6 months"
- "Stores with high volume but low revenue"
- "Are newer films performing better than older ones?"

🔍 Tests: derived metrics, implicit comparisons, multi-step reasoning

⸻

🧠 Ambiguous-by-design (semantic layer torture tests 😈)

These are gold for Lumen:
- "Top customers"
→ by revenue? rentals? frequency?
- "Best films"
→ revenue, rentals, ratings?
- "Inactive customers"
→ no rentals? no payments? since when?
- "Sales by category"
→ payments? rentals?
- "Performance by region"
→ customer country or store location?

🔍 Tests: clarification prompts, default semantics, explainability

⸻

🔁 Conversational follow-ups (agent memory)
- "Break that down by store"
- "Only include last quarter"
- "Exclude inactive customers"
- "Now compare that to last year"
- "Why did that change?"
- "Show me the top 5 instead"

🔍 Tests: context retention, query refinement, delta reasoning