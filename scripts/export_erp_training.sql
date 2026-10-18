-- تصدير قراءات ERP المعتمدة مع صورها لتدريب قارئ السطر.
-- يشغّله المالك فقط. الناتج بيانات خاصة: لا يُرفع إلى git (ADR-0004).
-- الوسم = الجزء الصحيح فقط (العشري لا يُقرأ أبداً).
\copy (
  SELECT
    r.id                                   AS reading_id,
    r.meter_id                             AS meter_id,          -- للفصل حسب العداد
    r.photo_storage_key                    AS photo_key,
    r.photo_checksum_sha256                AS photo_sha256,       -- لاستبعاد الصور الـ 49
    floor(r.current_reading_kwh)::bigint   AS reading_int,
    r.reading_source                       AS source,
    r.captured_at                          AS captured_at
  FROM billing_meter_readings r
  WHERE r.status = 'confirmed'
    AND r.photo_storage_key IS NOT NULL
    AND r.meter_id IS NOT NULL
    AND r.reading_result = 'actual'
) TO 'erp_training_export.csv' WITH CSV HEADER;
