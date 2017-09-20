def get_roles_as_list(desc):
    roles = desc.get("role", [])
    if roles:
        roles = [roles]
    roles.extend(desc.get("roles", []))
    return roles


def gen_rsc(roles):
    for _, hosts in roles.items():
        for host in hosts:
            yield host
