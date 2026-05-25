# Backend App Reference

Этот справочник сейчас сфокусирован на самой непонятной части backend — папке `services`.

`api` отвечает за HTTP-ручки, `models` описывает таблицы, `core` хранит настройки и безопасность. А вот `services` — это место, где происходит реальная логика системы: камеры читают кадры, YOLO ищет человека, InsightFace узнаёт лицо, Re-ID сравнивает одежду, события пишутся в журналы, а маршрут строится по графу здания.

Начинай отсюда:

- [services/README.md](services/README.md) — общая карта сервисов.
- [services/stream_manager.md](services/stream_manager.md) — как живые камеры читают кадры и запускают распознавание.
- [services/recognition_service.md](services/recognition_service.md) — как работает распознавание лица.
- [services/reid_service.md](services/reid_service.md) — как YOLO и OSNet ищут гостя по силуэту/одежде.
- [services/guest_route_service.md](services/guest_route_service.md) — как строится вероятный маршрут гостя.

