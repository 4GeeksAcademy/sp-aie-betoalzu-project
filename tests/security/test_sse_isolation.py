import asyncio

from services.api.rfp_intake.sse import RfpSseManager


def test_sse_events_are_isolated_by_owner_and_reach_all_owner_tabs():
    async def scenario():
        manager = RfpSseManager()
        first_id, first = await manager.subscribe(actor_id="owner-a")
        second_id, second = await manager.subscribe(actor_id="owner-a")
        other_id, other = await manager.subscribe(actor_id="owner-b")
        payload = {"ticket_id": "synthetic-ticket", "status": "analyzing"}

        await manager.publish("rfp_ticket_created", payload, actor_id="owner-a")

        assert first.get_nowait()["data"] == payload
        assert second.get_nowait()["data"] == payload
        assert other.empty()
        await manager.unsubscribe(first_id)
        await manager.unsubscribe(second_id)
        await manager.unsubscribe(other_id)

    asyncio.run(scenario())
