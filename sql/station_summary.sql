-- Busiest stations with member share and average trip length.
SELECT s.station_id,
       s.name,
       s.capacity,
       count(*)                                          AS trips,
       round(avg(CASE WHEN t.member_casual = 'member' THEN 1.0 ELSE 0.0 END), 3) AS member_share,
       round(avg(date_diff('second', t.started_at, t.ended_at)) / 60.0, 1)       AS avg_minutes
FROM trips t
JOIN stations s ON s.station_id = t.start_station_id
GROUP BY 1, 2, 3
ORDER BY trips DESC
LIMIT 25;
