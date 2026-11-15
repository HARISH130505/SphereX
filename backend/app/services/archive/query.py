"""
SPHEREx TAP ADQL query builder.
"""
def build_cone_search_adql(ra: float, dec: float, radius_deg: float = 0.1, collection: str = "spherex_qr3") -> str:
    """Builds IVOA TAP ADQL statement for spatial cone search."""
    return (
        f"SELECT * FROM ivoa.ObsCore "
        f"WHERE 1=CONTAINS(POINT('ICRS', s_ra, s_dec), "
        f"CIRCLE('ICRS', {ra}, {dec}, {radius_deg})) "
        f"ORDER BY t_min ASC"
    )
