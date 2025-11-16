def wei_to_eth(value):
    try:
        return int(value) / 1e18
    except:
        return 0.0
