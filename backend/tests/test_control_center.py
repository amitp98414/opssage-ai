from app.services.control_center import add_event, clear_events, control_center_status, list_events


def test_control_center_event_lifecycle():
    clear_events()

    event = add_event(
        event_type="task.started",
        status="running",
        message="Test task started.",
        agent="Test Agent",
        task_id="test-task",
    )

    assert event["type"] == "task.started"
    assert event["status"] == "running"
    assert list_events(1)[0]["task_id"] == "test-task"

    status = control_center_status()
    assert status["system"] == "online"
    assert status["active_agent"] == "Test Agent"
    assert status["event_count"] == 1

    clear_events()
    assert list_events() == []
