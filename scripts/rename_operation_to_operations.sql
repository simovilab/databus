-- Recover from app rename: operation -> operations
-- Renames physical tables and sequences and updates Django bookkeeping rows.
-- Wrapped in a single transaction; ON_ERROR_STOP=1 should be set on the psql side.

BEGIN;

-- 1. Tables (12 total)
ALTER TABLE operation_company              RENAME TO operations_company;
ALTER TABLE operation_operator             RENAME TO operations_operator;
ALTER TABLE operation_operator_company     RENAME TO operations_operator_company;
ALTER TABLE operation_dataprovider         RENAME TO operations_dataprovider;
ALTER TABLE operation_dataprovider_company RENAME TO operations_dataprovider_company;
ALTER TABLE operation_vehicle              RENAME TO operations_vehicle;
ALTER TABLE operation_equipment            RENAME TO operations_equipment;
ALTER TABLE operation_equipmentlog         RENAME TO operations_equipmentlog;
ALTER TABLE operation_run                  RENAME TO operations_run;
ALTER TABLE operation_position             RENAME TO operations_position;
ALTER TABLE operation_progression          RENAME TO operations_progression;
ALTER TABLE operation_occupancy            RENAME TO operations_occupancy;

-- 2. Sequences (7 total — only int-PK and M2M tables have them;
--    Company/Operator/DataProvider/Vehicle have CharField PKs, Equipment has UUID PK)
ALTER SEQUENCE operation_operator_company_id_seq     RENAME TO operations_operator_company_id_seq;
ALTER SEQUENCE operation_dataprovider_company_id_seq RENAME TO operations_dataprovider_company_id_seq;
ALTER SEQUENCE operation_equipmentlog_id_seq         RENAME TO operations_equipmentlog_id_seq;
ALTER SEQUENCE operation_run_id_seq                  RENAME TO operations_run_id_seq;
ALTER SEQUENCE operation_position_id_seq             RENAME TO operations_position_id_seq;
ALTER SEQUENCE operation_progression_id_seq          RENAME TO operations_progression_id_seq;
ALTER SEQUENCE operation_occupancy_id_seq            RENAME TO operations_occupancy_id_seq;

-- 3. Django bookkeeping
UPDATE django_migrations   SET app       = 'operations' WHERE app       = 'operation';
UPDATE django_content_type SET app_label = 'operations' WHERE app_label = 'operation';

-- 4. Sanity checks (raise exception if anything is left over)
DO $$
DECLARE
    leftover_tables    int;
    leftover_sequences int;
    leftover_migs      int;
    leftover_cts       int;
BEGIN
    SELECT count(*) INTO leftover_tables    FROM pg_tables       WHERE tablename    LIKE 'operation\_%' ESCAPE '\';
    SELECT count(*) INTO leftover_sequences FROM pg_sequences    WHERE sequencename LIKE 'operation\_%' ESCAPE '\';
    SELECT count(*) INTO leftover_migs      FROM django_migrations   WHERE app       = 'operation';
    SELECT count(*) INTO leftover_cts       FROM django_content_type WHERE app_label = 'operation';

    IF leftover_tables    > 0 THEN RAISE EXCEPTION 'leftover operation_* tables: %',    leftover_tables;    END IF;
    IF leftover_sequences > 0 THEN RAISE EXCEPTION 'leftover operation_* sequences: %', leftover_sequences; END IF;
    IF leftover_migs      > 0 THEN RAISE EXCEPTION 'leftover django_migrations rows for app=operation: %',    leftover_migs;      END IF;
    IF leftover_cts       > 0 THEN RAISE EXCEPTION 'leftover django_content_type rows for app_label=operation: %', leftover_cts; END IF;
END $$;

COMMIT;
