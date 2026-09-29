-- Student-level rows are de-identified by design: the mart holds ids only,
-- and the dashboard only ever aggregates them.
select * from marts.student_attendance_summary
