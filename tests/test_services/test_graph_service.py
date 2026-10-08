from pathlib import Path
from datetime import datetime
from models.schedule import CalendarEvent
from services.graph_service import GraphService

def test_graph_service_generates_file(tmp_path, kyiv_tz):
    out_file = tmp_path / "test_outage_chart.png"
    graph_service = GraphService("Europe/Kyiv")

    planned = [
        CalendarEvent(
            start=kyiv_tz.localize(datetime(2026, 3, 4, 9, 0)),
            end=kyiv_tz.localize(datetime(2026, 3, 4, 13, 0))
        )
    ]
    scheduled = []

    res_path = graph_service.generate_chart(planned, scheduled, str(out_file))
    assert Path(res_path).exists()
    assert Path(res_path).stat().st_size > 1000  # Файл изображения валидного размера
