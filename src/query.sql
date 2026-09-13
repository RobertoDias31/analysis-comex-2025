SELECT
    SUM(CASE WHEN VL_FOB IS NULL THEN 1 ELSE 0 END) AS null_fob,
    SUM(CASE WHEN VL_FRETE IS NULL THEN 1 ELSE 0 END) AS null_frete,
    SUM(CASE WHEN CO_PAIS IS NULL THEN 1 ELSE 0 END) AS null_pais
FROM tb_imp;

SELECT
    SUM(CASE WHEN VL_FOB <= 0 THEN 1 ELSE 0 END) AS fob_zero_ou_negativo,
    SUM(CASE WHEN VL_FRETE < 0 THEN 1 ELSE 0 END) AS frete_negativo
FROM tb_imp;


DROP TABLE IF EXISTS imp_tratada;

CREATE TABLE imp_tratada AS
SELECT
    imp.CO_ANO,
    imp.CO_MES,
    imp.CO_NCM,
    imp.CO_UNID,
    imp.CO_PAIS,
    imp.SG_UF_NCM,
    imp.CO_VIA,
    imp.CO_URF,
    imp.QT_ESTAT,
    imp.KG_LIQUIDO,
    imp.VL_FOB,
    imp.VL_FRETE,
    imp.VL_SEGURO,

    CASE WHEN imp.VL_FOB <= 0 THEN 1 ELSE 0 END AS flag_fob_zerado,

    CASE WHEN imp.KG_LIQUIDO = 0 THEN 1 ELSE 0 END AS flag_peso_zerado,

    CASE
        WHEN imp.VL_FOB > 0
        THEN ROUND(imp.VL_FRETE * 1.0 / imp.VL_FOB, 4)
        ELSE NULL
    END AS pct_frete_fob,

    pais.NO_PAIS,

    bloco_agg.NO_BLOCO,

    unid.NO_UNID,
    unid.SG_UNID,

    urf.NO_URF,

    via.NO_VIA,

    ncm.NO_NCM_POR,

    cgce.NO_CGCE_N1,
    cgce.NO_CGCE_N2,
    cgce.NO_CGCE_N3

FROM tb_imp AS imp

LEFT JOIN tb_pais AS pais
    ON imp.CO_PAIS = pais.CO_PAIS

LEFT JOIN (
    SELECT
        CO_PAIS,
        GROUP_CONCAT(NO_BLOCO, ', ') AS NO_BLOCO
    FROM tb_pais_bloco
    GROUP BY CO_PAIS
) AS bloco_agg
    ON imp.CO_PAIS = bloco_agg.CO_PAIS

LEFT JOIN tb_ncm_unidades AS unid
    ON imp.CO_UNID = unid.CO_UNID

LEFT JOIN tb_urf AS urf
    ON imp.CO_URF = urf.CO_URF

LEFT JOIN tb_via AS via
    ON imp.CO_VIA = via.CO_VIA

LEFT JOIN tb_ncm AS ncm
    ON imp.CO_NCM = ncm.CO_NCM

LEFT JOIN tb_ncm_cgce AS cgce
    ON ncm.CO_CGCE_N3 = cgce.CO_CGCE_N3;


CREATE INDEX idx_imp_trat_pais ON imp_tratada(CO_PAIS);
CREATE INDEX idx_imp_trat_via ON imp_tratada(CO_VIA);
CREATE INDEX idx_imp_trat_ano_mes ON imp_tratada(CO_ANO, CO_MES);
CREATE INDEX idx_imp_trat_ncm ON imp_tratada(CO_NCM);
CREATE INDEX idx_imp_trat_cgce_n1 ON imp_tratada(NO_CGCE_N1);


SELECT COUNT(*) AS total_linhas FROM imp_tratada;

SELECT COUNT(*) AS ncm_sem_nome FROM imp_tratada WHERE NO_NCM_POR IS NULL;

SELECT COUNT(*) AS cgce_sem_nome FROM imp_tratada WHERE NO_CGCE_N1 IS NULL;

SELECT SUM(VL_FOB) AS total_fob FROM imp_tratada;

SELECT * FROM imp_tratada