"""Build the standalone teaching note from verified source references."""
from pathlib import Path
import json
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.opc.constants import RELATIONSHIP_TYPE as RT

ROOT = Path(__file__).resolve().parent
ROOT.mkdir(parents=True, exist_ok=True)
REFS = [
 {"id":1,"author":"LaMarsh, Jeff / New Gold New Afton","year":"2022","title":"New Afton’s Learnings During the Implementation of Sandvik’s Battery-Electric Mobile Fleet","location":"Slide 16","url":"https://www.mining.sandvik/globalassets/campaigns/innovation-in-mining/pdf/wednesday-3-jeff-lamarsh-new-afton-bev.pdf#page=16","supports":"Historical Route A dimensions and reported net battery consumption; no rolling-resistance measurement supplied."},
 {"id":2,"author":"Caterpillar","year":"2022","title":"AD30 Underground Mining Truck Technical Specifications","location":"AEXQ3472 (05-2022), page 5, Gradeability/Speed/Rimpull","url":"https://www.empire-cat.com/sites/default/files/products/documents/CM20220523-b2ea9-e564b.pdf#page=5","supports":"General guide of 2 percent rolling resistance for underground applications; not New Afton or Z50 field data."},
 {"id":3,"author":"Global Mining Guidelines Group","year":"2022","title":"Recommended Practices for Battery Electric Vehicles in Underground Mining","location":"Version 3, GMG07-EM-2022, Table 9.2, printed page 94 (PDF page 107)","url":"https://gmggroup.org/wp-content/uploads/2024/08/Trolley-Assist-Systems.pdf#page=107","supports":"Example rolling resistance of 3 percent, qualified as based on situation; not a required or measured universal value."},
 {"id":4,"author":"Sandvik","year":"2023","title":"TH550B Battery Electric Truck Technical Specification","location":"TS3-TH550B-01/ENG/METRIC, page 8, Grade performance","url":"https://www.mining.sandvik/globalassets/products/underground-loaders-and-trucks/pdf/th550b-technical-specifications-english.pdf#page=8","supports":"Assumed 3 percent rolling resistance in underground BEV performance estimates. Different vehicle and battery system from the historical Z50."},
 {"id":5,"author":"Caterpillar","year":"n.d.","title":"Rolling Resistance Factors","location":"Rolling Resistance Percentage Table, surfaces A to C","url":"https://www.cat.com/en_US/articles/ci-articles/rolling-resistance-factors.html","supports":"4 percent for rutted/deforming dirt with about 25 mm penetration or flexing; 1.2 to 1.5 percent for very hard smooth surfaces. Generic estimating guidance."},
 {"id":6,"author":"Kryton International","year":"n.d.","title":"New Afton Mine","location":"Project case study, Background and Solution","url":"https://www.kryton.com/projects/new-afton-mine/","supports":"Concrete underground passages and wear in truck turning/dumping areas. Supplier report, not a Route A pavement survey or rolling-resistance test."},
]

def hyperlink(paragraph, text, url):
    link = OxmlElement('w:hyperlink')
    link.set(qn('r:id'), paragraph.part.relate_to(url, RT.HYPERLINK, is_external=True))
    run = OxmlElement('w:r'); props = OxmlElement('w:rPr')
    col = OxmlElement('w:color'); col.set(qn('w:val'),'175A89'); props.append(col)
    under = OxmlElement('w:u'); under.set(qn('w:val'),'single'); props.append(under)
    run.append(props); node=OxmlElement('w:t'); node.text=text; run.append(node)
    link.append(run); paragraph._p.append(link)

doc = Document()
s = doc.sections[0]
s.page_width=Inches(8.5); s.page_height=Inches(11)
s.top_margin=s.bottom_margin=Inches(.65)
s.left_margin=s.right_margin=Inches(.75)
s.header_distance=s.footer_distance=Inches(.3)
for name in ['Normal','Title','Subtitle','Heading 1','Heading 2','Caption']:
    st=doc.styles[name]; st.font.name='Calibri'; st.font.color.rgb=RGBColor(0,0,0)
for st in doc.styles:
    for border in list(st.element.iter(qn('w:pBdr'))):
        border.getparent().remove(border)
doc.styles['Normal'].font.size=Pt(11)
doc.styles['Normal'].paragraph_format.space_after=Pt(7)
doc.styles['Normal'].paragraph_format.line_spacing=1.08
doc.styles['Title'].font.size=Pt(21)
doc.styles['Title'].paragraph_format.space_after=Pt(7)
doc.styles['Heading 1'].font.size=Pt(14)
doc.styles['Heading 1'].paragraph_format.space_before=Pt(12)
doc.styles['Heading 1'].paragraph_format.space_after=Pt(6)
doc.styles['Caption'].font.size=Pt(9)
doc.core_properties.title='New Afton haulage experiment walkthrough'
doc.core_properties.subject='Rolling resistance assumptions and source evidence'
doc.core_properties.author=''
doc.core_properties.keywords='HAULSIM, New Afton, rolling resistance, assumptions'
footer=s.footer.paragraphs[0]; footer.alignment=WD_ALIGN_PARAGRAPH.RIGHT
footer.add_run('Experiment walkthrough | ')
field=OxmlElement('w:fldSimple'); field.set(qn('w:instr'),'PAGE'); footer._p.append(field)

doc.add_paragraph('New Afton haulage experiment walkthrough','Title')
doc.add_paragraph('Rolling resistance assumptions and source evidence','Subtitle')
doc.add_paragraph('Reference check dated 7 November 2026')
doc.add_paragraph('The nine HAULSIM cases use rolling resistance of 2%, 3% and 4% to test how changing resistance affects haulage energy and operating performance. These values are engineering sensitivity assumptions. They are not measurements of New Afton’s roads. This companion note explains the choice and provides the sources for supervisor review.')
doc.add_heading('The experiment represented',level=1)
doc.add_paragraph('The route is informed by New Afton’s historical Route A: approximately 1.5 km one way, 135 m of elevation change, and about 830 m at 16% grade [1]. The model completes the remaining geometry using assumptions. It is not a surveyed reconstruction of the mine.')
doc.add_paragraph('One truck carries 45 t. Three nominal battery-energy configurations (283.2, 354 and 424.8 kWh) are crossed with the three resistance values, giving nine cases. Each saved case runs for 120 minutes without charging, battery swapping or regenerative braking. Vehicle mass and available power change with the battery configuration, so these runs compare whole configurations rather than capacity alone.')
doc.add_heading('Why these three resistance values are defensible',level=1)
table=doc.add_table(rows=1, cols=3); table.alignment=WD_TABLE_ALIGNMENT.CENTER; table.autofit=False
widths=[.63,2.05,4.32]
for c,w in zip(table.columns,widths): c.width=Inches(w)
for c,t in zip(table.rows[0].cells,['Value','Role in the experiment','Source support and limit']): c.text=t
rows=[
 ('2%','Lower resistance case','Caterpillar recommends 2% as a general underground estimate [2]. This supports a plausible lower case, not a measured New Afton value or an absolute minimum.'),
 ('3%','Central reference case','GMG gives 3% as an example qualified by the situation [3]. Sandvik also assumes 3% for TH550B performance estimates [4]. The midpoint is a study choice, not a calibration result.'),
 ('4%','Higher resistance case','Caterpillar lists 4% for rutted or deforming dirt with about 25 mm penetration or flexing [5]. This supports a higher-resistance scenario, not a description of New Afton’s normal roads.'),
]
for row in rows:
    cells=table.add_row().cells
    for c,t in zip(cells,row): c.text=t
pr=table._tbl.tblPr
borders=OxmlElement('w:tblBorders')
for edge in ['top','left','bottom','right','insideH','insideV']:
    e=OxmlElement('w:'+edge); e.set(qn('w:val'),'single');e.set(qn('w:sz'),'4');e.set(qn('w:color'),'D9D9D9');borders.append(e)
pr.append(borders)
for i,row in enumerate(table.rows):
    trPr=row._tr.get_or_add_trPr(); trPr.append(OxmlElement('w:cantSplit'))
    if i==0: trPr.append(OxmlElement('w:tblHeader'))
    for j,cell in enumerate(row.cells):
        cell.width=Inches(widths[j]);cell.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
        tcPr=cell._tc.get_or_add_tcPr(); mar=OxmlElement('w:tcMar')
        for edge in ['top','left','bottom','right']:
            e=OxmlElement('w:'+edge);e.set(qn('w:w'),'85');e.set(qn('w:type'),'dxa');mar.append(e)
        tcPr.append(mar)
        if i==0:
            sh=OxmlElement('w:shd'); sh.set(qn('w:fill'),'E8EDF2');tcPr.append(sh)
        for p in cell.paragraphs:
            p.paragraph_format.space_after=Pt(0);p.paragraph_format.line_spacing=1.02
            if j==0:p.alignment=WD_ALIGN_PARAGRAPH.CENTER
            for r in p.runs:r.font.size=Pt(10);r.bold=(i==0)

doc.add_page_break()
doc.add_heading('What the assumptions mean in HAULSIM',level=1)
doc.add_paragraph('Road grade and rolling resistance are separate inputs. The 16% grade describes the uphill slope. The 2%, 3% and 4% settings describe increasing effective resistance to rolling at the tyre and road interface. The same route geometry is retained across all nine cases, with one resistance value applied uniformly within each case.')
doc.add_paragraph('Higher rolling resistance can increase tractive effort and energy demand and can affect speed where performance is limited. It is not a direct measurement of vibration, dust, humidity or battery temperature. Road condition, tyre type, inflation and loading all influence the effective resistance [3, 5].')
doc.add_paragraph('Figure 1 shows the reference case C100_RR03. To inspect it in HAULSIM, open Build, choose Individual selection, and click the road between two junctions. The Properties panel shows Grade = 16.00% and Rolling Resistance = 3.00%. The values identify the selected model segment; the screenshot is not a field measurement.')
p=doc.add_paragraph();p.alignment=WD_ALIGN_PARAGRAPH.CENTER
picture=p.add_run().add_picture(str(ROOT.parent/'native_haulsim/screenshots/01_road_grade_16_percent.png'),width=Inches(6.65))
crop=OxmlElement('a:srcRect');crop.set('b','66500')
fill=picture._inline.graphic.graphicData.pic.blipFill
fill.insert(1,crop)
picture.height=int(picture.height*.335)
doc.add_paragraph('Figure 1. Cropped detail of the actual HAULSIM Properties screenshot from the demonstration copy of C100_RR03. The selected segment is 29.64 m long; its grade is 16.00% and its assumed rolling resistance is 3.00%.','Caption')
doc.add_heading('What can be said about New Afton',level=1)
doc.add_paragraph('The operator presentation gives route geometry and consumption information but no rolling-resistance measurement [1]. A supplier case study describes concrete passages and wear in truck turning and dumping areas [6]. It does not identify the surface of the complete Route A. The mine therefore should not be described as uniformly soft or unpaved.')
doc.add_paragraph('The 2% to 4% range is a conditional comparison, not the full range of possible roads. Caterpillar gives approximately 1.2% to 1.5% for very hard, smooth surfaces [5]. A lower-resistance case could be considered if Route A is confirmed to have predominantly smooth concrete. Confirmation requires site-specific surface and tyre information or suitable operating measurements.')

doc.add_page_break()
doc.add_heading('Connection to the temperature calculations',level=1)
doc.add_paragraph('HAULSIM provides simulated event energy and duration. External code uses these outputs to estimate demand and generate a temperature response under stated battery assumptions. The rolling-resistance references support the haulage sensitivity inputs only. They do not validate the equivalent-current mapping, the resulting battery temperatures or thermal-runaway detection.')
doc.add_paragraph('The existing two-hour simulator outputs also require an external energy-reserve cutoff for feasible-delivery comparisons. In this walkthrough, source support for road resistance is kept separate from energy-accounting checks and from physical validation of the battery model.')
doc.add_heading('References and evidence limits',level=1)
for ref in REFS:
    p=doc.add_paragraph()
    r=p.add_run(f"[{ref['id']}] {ref['author']} ({ref['year']}). ");r.bold=True
    hyperlink(p,ref['title'],ref['url'])
    p.add_run('. '+ref['location']+'.')
    p=doc.add_paragraph(ref['supports']);p.paragraph_format.space_after=Pt(9)
    for r in p.runs:r.font.size=Pt(10)
doc.add_paragraph('Source titles above are clickable. The accompanying reference manifest preserves the URLs, evidence locations and limitations. This note documents the rationale for the saved cases; it does not report new simulation runs.')
doc.save(ROOT/'New_Afton_Rolling_Resistance_Walkthrough.docx')
(ROOT/'references.json').write_text(json.dumps({'checked_date':'2026-11-07','scope':'Source evidence for assumed rolling-resistance sensitivity cases; not measured New Afton values','references':REFS},indent=2,ensure_ascii=False),encoding='utf-8')
print(ROOT/'New_Afton_Rolling_Resistance_Walkthrough.docx')
