import pandas as pd
from rdkit.Chem import AllChem, PandasTools
from rdkit import Chem
from datetime import date
from typing import Optional, List
import operator
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

def floatify(value):
    try:
        return float(value)
    except Exception:
        return float('nan')

def prep(df: pd.DataFrame,
         header: Chem.Mol,
         mol_col: str,
         name_col: str,
         outfile: str='for_fragalysis.sdf',
         ref_mol_names: Optional[str]=None,
         ref_pdb_name: Optional[str]=None,
         extras: Optional[dict]=None,
         letter_trim: int=20) -> None:
    """
    Prepare a SDF file for Fragalysis.


    :param df: dataframe with molecules
    :param header: Chem.Mol generated by ``generate_header`` for example
    :param mol_col: name of the column containing the molecules
    :param name_col: name of the column containing the names
    :param outfile: name of the output file
    :param ref_mol_names: comma separated list of names of the reference molecules (for all hits). Ignored if present.
    :param ref_pdb_name: name of the protein to use. Ignored if present.
    :param extras: Extra fields to add to the SDF file, these need to be in the ``header`` Chem.Mol
    :return:
    """
    # no tuple columns
    assert isinstance(df, pd.DataFrame), f'{df} is not a DataFrame'
    df = df.rename(columns={c: ':'.join(map(str, c)) for c in df.columns if isinstance(c, tuple)}).copy()
    # sort inputs
    if 'ref_mols' in df.columns:
        pass
    elif ref_mol_names:
        df['ref_mols'] = ref_mol_names
    else:
        ValueError('ref_mol_names is None and ref_mols is not in df.columns')
    if 'original SMILES' in df.columns:
        pass
    else:
        df['original SMILES'] = df[mol_col].apply(AllChem.RemoveAllHs).apply(Chem.MolToSmiles)
    if 'ref_pdb' in df.columns:
        pass
    elif ref_pdb_name:
        df['ref_pdb'] = ref_pdb_name
    else:
        ValueError('ref_pdb is None and ref_pdb is not in df.columns')
    # deal with extras
    if extras is None:
        extra_fields = []
    elif extras is True:
        extras = []
        for col in df.columns:
            df[col] = df[col].apply(floatify)
            if df[col].fillna(0).apply(abs).sum() > 0:
                extras.append(col)
    elif isinstance(extras, dict):
        extra_fields = list(extras.keys())
    elif isinstance(extras, list):
        extra_fields = extras
    else:
        raise ValueError('extras should be a dict or a list')
    df = df.copy()
    df[name_col] = df[name_col].apply(str)\
                                .str.replace(r'\W', '_', regex=True)\
                                .apply(operator.itemgetter(slice(None, int(letter_trim))))
    with open(outfile, 'w') as sdfh:
        with Chem.SDWriter(sdfh) as w:
            w.write(header)
        PandasTools.WriteSDF(df, sdfh, mol_col, name_col,
                             ['ref_pdb', 'ref_mols', 'original SMILES'] + extra_fields)

def floatify_columns(df: pd.DataFrame, columns: List[str]) -> pd.DataFrame:
    df = df.copy()
    for col in df.columns:
        df[col] = df[col].apply(floatify)

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
    if extras is None:
        extras = {}
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


class DummyMasker:
    """
    Copied form rdkit_to_params.utils !

    A context manager that allows operations on a mol containing dummy atoms (R/*) that
    otherwise would raise an RDKit error.
    It simply masks and unmasks the dummy atoms.

    >>> mol = Chem.MolFromSmiles('*CCC(C)C')
    >>> with DummyMasker(mol):
    >>>     AllChem.EmbedMolecule(mol)

    The input options for dummy maker are ``mol`` (Chem.Mol),
    ``placekeeper_zahl`` (Z for atomic number),
    and ``blank_Gasteiger`` to make the dummy atom's '_GasteigerCharge' property zero if present.
    The Zahl of the placekeeping element will affect the Gasteiger partial chargers of nearby atoms though.
    """

    def __init__(self,
                 mol: Chem.Mol,
                 placekeeper_zahl:int=6,
                 blank_Gasteiger:bool=True):
        self.mol = mol
        self.is_masked = False
        self.zahl = int(placekeeper_zahl)
        self.blank_Gasteiger = bool(blank_Gasteiger)
        self.dummies = list(  mol.GetAtomsMatchingQuery(Chem.rdqueries.AtomNumEqualsQueryAtom(0))  )

    def mask(self):
        for dummy in self.dummies:
            dummy.SetAtomicNum(self.zahl)
            dummy.SetBoolProp('dummy', True)
            dummy.SetHybridization(Chem.HybridizationType.SP3)
        self.is_masked = True

    def unmask(self):
        for dummy in self.dummies:
            assert dummy.HasProp('dummy'), 'The atoms have changed somehow? (weird cornercase)'
            dummy.SetAtomicNum(0)
            if dummy.HasProp('_GasteigerCharge') and self.blank_Gasteiger:
                dummy.SetDoubleProp('_GasteigerCharge', 0.)
        self.is_masked = False

    def __enter__(self):
        self.mask()
        return self

    def __exit__(self, exc_type: Exception, exc_value: str, exc_traceback: 'bultins.traceback'):
        self.unmask()