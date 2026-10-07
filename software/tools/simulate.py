#!/usr/bin/env python3
"""
simulate.py - try the whole management-bus stack on any computer, no Pis needed.

It wires a bus master and several worker agents to an in-memory "RS-485 wire",
then plays out a short story: three nodes boot, a fourth is hot-added,
one is unplugged, and the controller sends an identify command.

    python3 software/tools/simulate.py
"""
import logging
import os
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(HERE, "..", d) for d in ("common", "controller", "worker")]

import picase_bus as pb          # noqa: E402
from bus_master import Master    # noqa: E402
from bus_agent import Agent      # noqa: E402

logging.basicConfig(level=logging.INFO, format="  %(name)s: %(message)s")


def start_agent(hub, slot):
    agent = Agent(hub.endpoint(), slot, led_gpio=None, dry_run=True,
                  info_override={"h": f"picase-node{slot:02d}", "ip": f"10.42.0.{100 + slot}",
                                 "m": "RPi 5 B (sim)"})
    threading.Thread(target=agent.run, daemon=True).start()
    return agent


def table(master):
    for n in master.handle_command({"cmd": "status"})["nodes"]:
        if n["online"] or n["info"]:
            s = n["stats"]
            print(f"    slot {n['slot']:02d}  {'online ' if n['online'] else 'OFFLINE'} "
                  f"{n['info'].get('h'):<14} {n['info'].get('ip'):<12} "
                  f"temp={s.get('t')}  load={s.get('l')}  power={s.get('thr')}")


def passes(master, n):
    for _ in range(n):
        master.step()


def main():
    hub = pb.SimHub()
    master = Master(hub.endpoint(), slots=range(1, 8), reply_timeout=0.05,
                    stats_every=0.0, manage_hosts=False, state_path=None)

    print("\n1) Power on: workers in slots 1, 2 and 5")
    agents = {s: start_agent(hub, s) for s in (1, 2, 5)}
    passes(master, 2)
    table(master)

    print("\n2) Open the lid and hot-add a Pi into slot 7")
    agents[7] = start_agent(hub, 7)
    passes(master, 2)
    table(master)

    print("\n3) Pull the Pi out of slot 2")
    agents[2].bus.unplugged = True
    passes(master, 4)
    table(master)

    print("\n4) casectl identify 5")
    print("   ", master.handle_command({"cmd": "identify", "slot": 5}))
    print("\n5) casectl reboot all  (dry run - nothing actually reboots)")
    print("   ", master.handle_command({"cmd": "reboot", "slot": "all"}))

    print("\nEvents:")
    for ev in master.events:
        print("   ", ev)
    online = sorted(s for s, n in master.nodes.items() if n.online)
    assert online == [1, 5, 7], online
    print("\nSimulation OK - online slots:", online)


if __name__ == "__main__":
    main()
