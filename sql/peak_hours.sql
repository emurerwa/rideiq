-- Average trips per hour of day, weekday vs weekend.
SELECT extract('hour' FROM started_at)                         AS hour_of_day,
       CASE WHEN dayofweek(started_at) IN (0, 6) THEN 'weekend' ELSE 'weekday' END AS day_type,
       count(*) * 1.0 / count(DISTINCT CAST(started_at AS DATE)) AS avg_trips
FROM trips
GROUP BY 1, 2
ORDER BY 2, 1;
