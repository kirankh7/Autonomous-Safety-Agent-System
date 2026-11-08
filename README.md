# Capstone Project: Autonomous Vehicle Intercommunication Safety Agent System

**Author:** Kiran Haridas
**Repository:** [github.com/kirankh7/Autonomous-Safety-Agent-System](https://github.com/kirankh7/Autonomous-Safety-Agent-System)
**Agent Option:** Research Assistant

## Overview

I propose to build an **Autonomous Vehicle Intercommunication Safety Agent System** that helps autonomous and self-driving vehicles share safety information across a fleet. The goal of the agent is to make roads safer by detecting, analyzing, verifying, and communicating unexpected road conditions or hazards to other vehicles that may encounter the same situation.

The intended users are autonomous vehicle operators, fleet managers, transportation organizations, and autonomous vehicles operating on public roads.

## Problem

An autonomous vehicle normally makes driving decisions using its own cameras, sensors, maps, and onboard models. However, there are situations where the vehicle may not have enough visibility or information to react safely.

For example, imagine a vehicle traveling through dense fog where visibility is limited. Another vehicle 400–600 meters ahead may detect a major accident, stopped vehicle, debris, flooding, or another unexpected obstacle in the road. The approaching vehicle may not yet be able to see the hazard through its own sensors or cameras. If that information could be communicated quickly and reliably across the fleet, the approaching vehicle could prepare for the situation earlier.

The proposed agent acts as a **shared safety intelligence layer** between vehicles.

## Why a Stand-Alone Language Model Is Not Enough

A standalone language model or simple prompting approach would not be sufficient because this problem requires continuous interaction with a changing environment and multiple sources of information.

The agent would need to process observations from multiple vehicles, determine whether observations are reliable, combine information from different sources, reason about the severity and location of a hazard, and communicate relevant information to other vehicles. It would also need to receive feedback and update its confidence as new information becomes available.

## Input / Environment

The agent would operate in an environment containing information from multiple autonomous and self-driving vehicles.

Potential inputs include:

- Vehicle camera images or video frames
- Synthetic vehicle sensor observations
- GPS and approximate vehicle location
- Vehicle direction and speed
- Road-condition information
- Traffic and accident information
- Weather and visibility conditions
- Public road and map data
- Historical road-hazard information
- Reports from other vehicles in the fleet

For this capstone, the data would be publicly available, synthetic, or anonymized and would not use proprietary autonomous vehicle data.

The environment is dynamic because road conditions can change quickly. A hazard reported by one vehicle may be confirmed, contradicted, or resolved by vehicles that encounter the same location later.

## Agent Actions

The agent would perform multiple actions to make progress toward its goal:

1. **Collect** observations from multiple vehicles and available public data sources.
2. **Analyze** observations to identify potential hazards such as accidents, potholes, debris, flooding, stopped vehicles, or unusual traffic conditions.
3. **Correlate** information from multiple vehicles that may be observing the same event.
4. **Verify** the hazard by comparing observations and checking whether the information is consistent.
5. **Estimate** the hazard's location and relevance, including its approximate distance and direction from approaching vehicles.
6. **Assess** confidence and severity based on the available evidence.
7. **Generate** a structured safety alert when sufficient evidence exists.
8. **Communicate** the alert to vehicles approaching the affected area.
9. **Monitor** subsequent observations to determine whether the hazard is still present or has been cleared.
10. **Update** the event information as new observations and feedback become available.

For example, if multiple vehicles independently report an accident approximately 500 meters ahead, the agent could correlate their observations and increase confidence that the event is real. It could then communicate a safety alert to approaching vehicles. The vehicle's existing driving system could use that information as an additional environmental input when making its own driving decisions.

## Feedback and Continuous Improvement

Feedback would guide the agent's behavior across multiple steps. Vehicles that receive an alert could later report whether the hazard was actually present, whether the location was accurate, and whether the condition had changed.

If multiple vehicles confirm the same hazard, the agent could increase confidence in the event. If subsequent vehicles report that no hazard exists, the agent could reduce confidence or mark the event as resolved.

Over time, this feedback loop would allow the system to improve how it evaluates reports and reduce false alerts.

## Long-Term Vision

The long-term vision is to create a shared safety intelligence layer across autonomous vehicles. Instead of every vehicle relying only on what its own sensors can currently see, vehicles could benefit from verified observations collected by other vehicles.

The system could eventually provide a continuously updated understanding of road conditions and unexpected hazards, helping autonomous vehicles respond earlier to situations that may not yet be visible to their own sensors.

## Working Prototype

The working agent application (FastAPI + LangGraph backend, React dashboard) lives in [`autonomous-vehicle-agent/`](autonomous-vehicle-agent/README.md) ([view on GitHub](https://github.com/kirankh7/Autonomous-Safety-Agent-System/tree/main/autonomous-vehicle-agent)). See its README for how to run it and how to demonstrate the five hazard scenarios.
