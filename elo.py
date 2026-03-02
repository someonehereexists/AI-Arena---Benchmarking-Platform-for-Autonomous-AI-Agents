from registry import find_agent

DEFAULT_ELO = 1000
K_FACTOR = 32


def expected_score(ra, rb):
    return 1 / (1 + 10 ** ((rb - ra) / 400))


def update_elo(rating, expected, actual):
    return round(rating + K_FACTOR * (actual - expected), 2)


def pairwise_elo_update(registry, builder) -> None:
    """
    Updates ELO in registry AND writes match ELO data into builder.agents
    builder.agents[agent_id]["elo"] = {before, after, delta}
    """

    agent_ids = list(builder.agents.keys())

    # Capture starting ELOs
    elo_before = {}
    for a_id in agent_ids:
        agent = find_agent(registry, agent_id=a_id)
        elo_before[a_id] = agent.get("elo", DEFAULT_ELO) if agent else DEFAULT_ELO

    # Pairwise comparisons
    for i in range(len(agent_ids)):
        for j in range(i + 1, len(agent_ids)):
            a, b = agent_ids[i], agent_ids[j]

            agent_a = find_agent(registry, agent_id=a)
            agent_b = find_agent(registry, agent_id=b)
            if not agent_a or not agent_b:
                continue

            ra = agent_a.get("elo", DEFAULT_ELO)
            rb = agent_b.get("elo", DEFAULT_ELO)

            ea = expected_score(ra, rb)
            eb = expected_score(rb, ra)

            sa = builder.agents[a]["score"]
            sb = builder.agents[b]["score"]

            if sa > sb:
                aa, ab = 1, 0
            elif sa < sb:
                aa, ab = 0, 1
            else:
                aa, ab = 0.5, 0.5

            new_ra = update_elo(ra, ea, aa)
            new_rb = update_elo(rb, eb, ab)

            agent_a["elo"] = new_ra
            agent_b["elo"] = new_rb

    # Capture final ELOs and write into builder
    elo_after = {}
    elo_delta = {}

    for a_id in agent_ids:
        agent = find_agent(registry, agent_id=a_id)

        before = elo_before.get(a_id, DEFAULT_ELO)
        after = agent.get("elo", DEFAULT_ELO) if agent else before
        delta = round(after - before, 2)

        builder.agents[a_id]["elo"] = {
            "before": before,
            "after": after,
            "delta": delta,
        }
