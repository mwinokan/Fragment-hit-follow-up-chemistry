import pandas as pd
from rdkit.Chem import AllChem, PandasTools
from rdkit import Chem
from datetime import date
from typing import Optional
def align(mol_series: pd.Series, ref_hit: Chem.Mol, used_hit: Chem.Mol) -> pd.Series:
    """
    It happens...
    Sometimes you might have a series of followups that are in frame with a hit,
    but that is not the same as in Fragalysis.
    This function aligns a pd.Series of molecules the former to the latter's frame.

    :param mol_series:
    :param ref_hit:
    :param used_hit:
    :return:
    """
    rototrans = AllChem.GetAlignmentTransform(used_hit, ref_hit)[1]
    new_mols = mol_series.apply(lambda mol: Chem.Mol())
    new_mols.apply(lambda mol: AllChem.TransformConformer(mol.GetConformer(), rototrans))
    return new_mols

def prep(df: pd.DataFrame,
         header: Chem.Mol,
         mol_col: str,
         name_col: str,
         outfile: str='for_fragalysis.sdf',
         ref_mol_names: Optional[str]=None,
         ref_pdb: Optional[str]=None,
         extras: Optional[dict]=None) -> None:
    """
    Prepare a SDF file for Fragalysis.


    :param df: dataframe with molecules
    :param header: Chem.Mol generated by ``generate_header`` for example
    :param mol_col: name of the column containing the molecules
    :param name_col: name of the column containing the names
    :param outfile: name of the output file
    :param ref_mol_names: comma separated list of names of the reference molecules (for all hits). Ignored if present.
    :param ref_pdb: name of the protein to use. Ignored if present.
    :param extras: Extra fields to add to the SDF file, these need to be in the ``header`` Chem.Mol
    :return:
    """
    if 'ref_mol' in df.columns:
        pass
    elif ref_mol_names:
        df['ref_mols'] = ref_mol_names
    else:
        ValueError('ref_mol_names is None and ref_mol is not in df.columns')
    if 'original SMILES' in df.columns:
        pass
    else:
        df['original SMILES'] = df[mol_col].apply(Chem.MolToSmiles)
    if 'ref_pdb' in df.columns:
        pass
    elif ref_pdb:
        df['ref_pdb'] = ref_pdb
    else:
        ValueError('ref_pdb is None and ref_pdb is not in df.columns')
    if extras is None:
        extra_fields = []
    elif isinstance(extras, dict):
        extra_fields = list(extras.keys())
    elif isinstance(extras, list):
        extra_fields = extras
    else:
        raise ValueError('extras should be a dict or a list')
    with open(outfile, 'w') as sdfh:
        with Chem.SDWriter(sdfh) as w:
            w.write(header)
        PandasTools.WriteSDF(df, sdfh, mol_col, name_col,
                             ['ref_pdb', 'ref_mols', 'original SMILES'] + extra_fields)

def generate_header(method: str,
                    ref_url: Optional[str]= 'https://www.example.com',
                    submitter_name: Optional[str]= 'unknown',
                    submitter_email: Optional[str] = 'a@b.c',
                    submitter_institution: Optional[str] = 'Nowehere',
                    generation_date: Optional[str] = str(date.today()),
                    smiles: Optional[str] = 'CN1C=NC2=C1C(=O)N(C(=O)N2C)C',
                    extras: Optional[dict] = None) -> Chem.Mol:
    """
    Generate a header Chem.Mol for a SDF file in the ver_1.2 style.
    cf. https://discuss.postera.ai/t/providing-computed-poses-for-others-to-look-at/1155/6

    :param method: **Unique** and compulsory. Note that it will be bleached.
    :param ref_url:
    :param submitter_name:
    :param submitter_email:
    :param submitter_institution:
    :param generation_date:
    :param smiles:
    :param extras:  A dictionary of extra properties to add to the header.
                    These will be present in all the molecules in the SDF for sortable tables!
    :return: Chem.Mol
    """
    bannermol = Chem.MolFromSmiles(smiles)
    bannermol.SetProp('_Name', 'ver_1.2')
    AllChem.EmbedMolecule(bannermol)
    for k, v in {'ref_url': ref_url,
                 'submitter_name': submitter_name,
                 'submitter_email': submitter_email,
                    'submitter_institution': submitter_institution,
                 'generation_date': generation_date,
                 'method': method,
                 }.items():
        bannermol.SetProp(k, v)
    for k, v in extras.items():
        bannermol.SetProp(k, str(v))
    return bannermol