-- Complete hourly grid of departures and arrivals per station (zeros included).
WITH bounds AS (
    SELECT date_trunc('hour', min(started_at)) AS t0,
           date_trunc('hour', max(started_at)) AS t1
    FROM trips
),
hours AS (
    SELECT unnest(generate_series(t0, t1, INTERVAL 1 HOUR)) AS hour
    FROM bounds
),
grid AS (
    SELECT s.station_id, h.hour
    FROM stations s
    CROSS JOIN hours h
),
dep AS (
    SELECT start_station_id AS station_id,
           date_trunc('hour', started_at) AS hour,
           count(*) AS departures
    FROM trips
    GROUP BY 1, 2
),
arr AS (
    SELECT end_station_id AS station_id,
           date_trunc('hour', ended_at) AS hour,
           count(*) AS arrivals
    FROM trips
    GROUP BY 1, 2
)
SELECT g.station_id,
       g.hour,
       coalesce(d.departures, 0) AS departures,
       coalesce(a.arrivals, 0)   AS arrivals,
       coalesce(a.arrivals, 0) - coalesce(d.departures, 0) AS net_flow
FROM grid g
LEFT JOIN dep d ON d.station_id = g.station_id AND d.hour = g.hour
LEFT JOIN arr a ON a.station_id = g.station_id AND a.hour = g.hour
ORDER BY g.station_id, g.hour;
