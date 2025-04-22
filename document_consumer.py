from flask import Flask, request, jsonify, send_file,Response
import requests
import os
import datetime
from request_body import *
import io
from flask_cors import CORS
import html
from bs4 import BeautifulSoup
import base64
import xml.sax.saxutils as xml_utils
import uuid

app = Flask(__name__)
CORS(app)
BASE_URL = "http://localhost:8084/xdstools7.12.0/sim/"
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

def log_response(endpoint, soap_request, response):
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    log_file = os.path.join(LOG_DIR, f"log_{endpoint}_{timestamp}.txt")
    with open(log_file, "w", encoding="utf-8") as log:
        log.write("==== SOAP Request ====\n")
        log.write(f"Request Body:\n{soap_request}\n\n")
        log.write("==== Response ====\n")
        log.write(f"Response Code: {response.status_code}\n")
        log.write(f"Response Body:\n{response.text}\n")
    return log_file


@app.route("/find_document", methods=["GET","POST"])
def find_document():

    request_body = request.json
    XDSDocumentEntryPatientId = request_body.get('XDSDocumentEntryPatientId')
    XDSDocumentEntryPatientId= html.escape(XDSDocumentEntryPatientId)
    print(XDSDocumentEntryPatientId)
    # XDSDocumentEntryType = request_body.get('XDSDocumentEntryType')
    # XDSDocumentEntryStatus1 = request_body.get('XDSDocumentEntryStatus1')
    # XDSDocumentEntryStatus2 = request_body.get('XDSDocumentEntryStatus2')

    soap_request = find_document_request.format(XDSDocumentEntryPatientId)
    headers = {"Content-Type": "application/soap+xml; charset=utf-8"}
    url = BASE_URL + "default__reg_01/reg/sq"
    response = requests.post(url, data=soap_request, headers=headers)
    soup = BeautifulSoup(response.text, "xml")

    # Extract Document IDs along with mimeType and corresponding DocA values
    documents = []
    for obj in soup.find_all("ExtrinsicObject"):
        doc_id = obj.get("id", "unknown")
        mime_type = obj.get("mimeType", "unknown")
        localized_string = obj.find("LocalizedString")
        doc_value = localized_string["value"] if localized_string else "unknown"
        
        documents.append({"id": doc_id, "mimeType": mime_type, "Title": doc_value})
    
    print("===================", response.text)
    return jsonify(
        {
            "status": response.status_code,
            "Documents": documents,
            # "response": response.text,
        }
    )

@app.route("/get_document", methods=["GET","POST"])
def get_document():
    request_body = request.json
    XDSDocumentEntryEntryUUID = request_body.get('XDSDocumentEntryEntryUUID')
    soap_request = get_document_request.format(XDSDocumentEntryEntryUUID)
    headers = {"Content-Type": "application/soap+xml; charset=utf-8"}
    url = BASE_URL + "default__reg_01/reg/sq"
    response = requests.post(url, data=soap_request, headers=headers)
    print(response.text)
    soup = BeautifulSoup(response.text, "xml")

    # Find the <ExternalIdentifier> element with the specific identificationScheme
    external_identifier = soup.find("ExternalIdentifier", {"identificationScheme": "urn:uuid:2e82c1f6-a085-4c72-9da3-8640a32e42ab"})
    if external_identifier and external_identifier.has_attr("value"):
        value = external_identifier["value"]
        print("Extracted Value:", value)
    else:
        value = None
        print("No value found for the specified identificationScheme.")
    # Extract RepositoryUniqueId
    repository_unique_id = None
    slot_element = soup.find("Slot", {"name": "repositoryUniqueId"})
    if slot_element:
        value_list = slot_element.find("ValueList")
        if value_list:
            value_element = value_list.find("Value")
            if value_element:
                repository_unique_id = value_element.text
                print("RepositoryUniqueId:", repository_unique_id)

    return jsonify({"status": response.status_code,"RepositoryUniqueId": repository_unique_id, "Document_uniqueId": value})


@app.route('/retrieve_document', methods=['POST'])
def retrieve_document():
    request_body = request.json
    # RepositoryUniqueId = request_body.get('RepositoryUniqueId')
    DocumentUniqueId = request_body.get('DocumentUniqueIds')[0]

    # Construct the SOAP request
    soap_request = retrieve_document_request.format(DocumentUniqueId)
    url = "http://localhost:8084/xdstools7.12.0/sim/default__rep_01/rep/ret"

    headers = {
        "Content-Type": "multipart/related; type=\"application/xop+xml\"; boundary=MIMEBoundary1234567890; start=\"<rootpart@soapui.org>\"; start-info=\"application/soap+xml\""
    }

    multipart_body = (
        "--MIMEBoundary1234567890\r\n"
        "Content-Type: application/xop+xml; charset=UTF-8; type=\"application/soap+xml\"\r\n"
        "Content-Transfer-Encoding: 8bit\r\n"
        "Content-ID: <rootpart@soapui.org>\r\n\r\n"
        f"{soap_request}\r\n"
        "--MIMEBoundary1234567890--\r\n"
    )

    # Send the request to the XDS repository
    response = requests.post(url, data=multipart_body, headers=headers)

    if response.status_code == 200:
        # Extract the PDF part from the MIME response
        boundary = b"--MIMEBoundary112233445566778899"
        parts = response.content.split(boundary)
        for part in parts:
            if b"Content-Type: application/pdf" in part:
                # Extract the PDF content
                pdf_start = part.find(b"%PDF")
                pdf_content = part[pdf_start:]
                return Response(pdf_content, content_type="application/pdf")
        return jsonify({"error": "PDF not found in response"}), 500
    else:
        return jsonify({"error": response.text}), response.status_code



def log_response(action, url, headers, request_body, response):
    log_file = os.path.join(LOG_DIR, f"log_{action}_{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.txt")
    with open(log_file, "w", encoding="utf-8") as log:
        log.write(f"==== {action.upper()} REQUEST ====\n")
        log.write(f"URL: {url}\n")
        log.write(f"Headers: {headers}\n")
        log.write(f"Request Body:\n{request_body}\n")
        log.write("==== RESPONSE ====\n")
        log.write(f"Response Code: {response.status_code}\n")
        log.write(f"Response Headers: {response.headers}\n")
        log.write(f"Response Body:\n{response.text}\n")
    print(f"Response logs saved to: {log_file}")


from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from io import BytesIO
from email.generator import BytesGenerator
import uuid
import requests
from flask import request, jsonify
import datetime
import base64

@app.route("/provide_register", methods=["POST"])
def provide_register():
    try:
        file = request.files.get("file")
        if not file:
            return jsonify({"error": "No file uploaded"}), 400

        patient_id = request.form.get("patientId") or "12335^^^&1.2.3.4.5&ISO"
        patient_id = xml_utils.escape(patient_id)
        mime_type = file.mimetype or "application/pdf"

        # Read document content
        document_content = file.read()
        document_content_b64 = base64.b64encode(document_content).decode('utf-8')

        # Generate required IDs
        submission_set_uuid = str(uuid.uuid4())
        document_uuid = str(uuid.uuid4())
        association_uuid = str(uuid.uuid4())
        submission_set_unique_id = f"2.25.{uuid.uuid4().int}"
        document_unique_id = f"2.25.{uuid.uuid4().int}"
        message_id = str(uuid.uuid4())
        boundary = f"MIMEBoundary_{uuid.uuid4().hex}"
        timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")

        # --- XDS.b Allowed Codes from Affinity Domain (from Node.js example) ---
        confidentiality_code = "R"
        confidentiality_code_display = "Restricted"
        confidentiality_code_scheme = "2.16.840.1.113883.5.25"
        confidentiality_code_uuid = "urn:uuid:f4f85eac-e6cb-4883-b524-f2705394840f"
        facility_type_code = "66280005"
        facility_type_code_display = "Private home-based care"
        facility_type_code_scheme = "2.16.840.1.113883.6.96"
        facility_type_code_uuid = "urn:uuid:f33fb8ac-18af-42cc-ae0e-ed0b0bdb91e1"
        class_code = "PLANS"
        class_code_display = "Treatment Plan or Protocol"
        class_code_scheme = "1.3.6.1.4.1.19376.1.2.6.1"
        class_code_uuid = "urn:uuid:41a5887f-8865-4c09-adf7-e362475b143a"
        type_code = "11502-2"
        type_code_display = "LABORATORY REPORT.TOTAL"
        type_code_scheme = "2.16.840.1.113883.6.1"
        type_code_uuid = "urn:uuid:f0306f51-975f-434e-a61c-c59651d33983"
        practice_setting_code = "Practice-D"
        practice_setting_code_display = "Pathology"
        practice_setting_code_scheme = "1.3.6.1.4.1.21367.2017.3"
        practice_setting_code_uuid = "urn:uuid:cccf5598-8b07-4b77-a05e-ae952c785ead"
        format_code = 'urn:ihe:iti:bppc:2007'
        format_code_display = 'urn:ihe:iti:bppc:2007'
        format_code_scheme = '1.3.6.1.4.1.19376.1.2.3'
        format_code_uuid = 'urn:uuid:a09d5840-386c-46f2-b5ad-9c3699a4309d'
        content_type_code = "394747008"
        content_type_code_display = "Health Authority"
        content_type_code_scheme = "2.16.840.1.113883.6.96"
        content_type_code_uuid = "urn:uuid:aa543740-bdda-424e-8c96-df4873be8500"

        # Build SOAP envelope with all required objects
        soap_xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://www.w3.org/2003/05/soap-envelope"
                  xmlns:wsa="http://www.w3.org/2005/08/addressing"
                  xmlns:xdsb="urn:ihe:iti:xds-b:2007"
                  xmlns:lcm="urn:oasis:names:tc:ebxml-regrep:xsd:lcm:3.0"
                  xmlns:rim="urn:oasis:names:tc:ebxml-regrep:xsd:rim:3.0">
  <soapenv:Header>
    <wsa:To>http://localhost:8084/xdstools7.12.0/sim/default__rep_01/rep/prb</wsa:To>
    <wsa:MessageID>{message_id}</wsa:MessageID>
    <wsa:Action soapenv:mustUnderstand="1">urn:ihe:iti:2007:ProvideAndRegisterDocumentSet-b</wsa:Action>
  </soapenv:Header>
  <soapenv:Body>
    <xdsb:ProvideAndRegisterDocumentSetRequest>
      <lcm:SubmitObjectsRequest>
        <rim:RegistryObjectList>
          <rim:ExtrinsicObject id="urn:uuid:{document_uuid}" mimeType="application/pdf" objectType="urn:uuid:7edca82f-054d-47f2-a032-9b2a5b5186c1">
            <rim:Slot name="creationTime"><rim:ValueList><rim:Value>{timestamp}</rim:Value></rim:ValueList></rim:Slot>
            <rim:Slot name="languageCode"><rim:ValueList><rim:Value>en-us</rim:Value></rim:ValueList></rim:Slot>
            <rim:Slot name="sourcePatientId"><rim:ValueList><rim:Value>{patient_id}</rim:Value></rim:ValueList></rim:Slot>
            <rim:Name><rim:LocalizedString value="Document"/></rim:Name>
            <rim:Description><rim:LocalizedString value="Document description"/></rim:Description>
            <rim:Classification classificationScheme="{class_code_uuid}" classifiedObject="urn:uuid:{document_uuid}" nodeRepresentation="{class_code}" objectType="urn:oasis:names:tc:ebxml-regrep:ObjectType:RegistryObject:Classification" id="urn:uuid:{uuid.uuid4()}">
              <rim:Slot name="codingScheme"><rim:ValueList><rim:Value>{class_code_scheme}</rim:Value></rim:ValueList></rim:Slot>
              <rim:Name><rim:LocalizedString value="{class_code_display}"/></rim:Name>
            </rim:Classification>
            <rim:Classification classificationScheme="{type_code_uuid}" classifiedObject="urn:uuid:{document_uuid}" nodeRepresentation="{type_code}" objectType="urn:oasis:names:tc:ebxml-regrep:ObjectType:RegistryObject:Classification" id="urn:uuid:{uuid.uuid4()}">
              <rim:Slot name="codingScheme"><rim:ValueList><rim:Value>{type_code_scheme}</rim:Value></rim:ValueList></rim:Slot>
              <rim:Name><rim:LocalizedString value="{type_code_display}"/></rim:Name>
            </rim:Classification>
            <rim:Classification classificationScheme="{confidentiality_code_uuid}" classifiedObject="urn:uuid:{document_uuid}" nodeRepresentation="{confidentiality_code}" objectType="urn:oasis:names:tc:ebxml-regrep:ObjectType:RegistryObject:Classification" id="urn:uuid:{uuid.uuid4()}">
              <rim:Slot name="codingScheme"><rim:ValueList><rim:Value>{confidentiality_code_scheme}</rim:Value></rim:ValueList></rim:Slot>
              <rim:Name><rim:LocalizedString value="{confidentiality_code_display}"/></rim:Name>
            </rim:Classification>
            <rim:Classification classificationScheme="{facility_type_code_uuid}" classifiedObject="urn:uuid:{document_uuid}" nodeRepresentation="{facility_type_code}" objectType="urn:oasis:names:tc:ebxml-regrep:ObjectType:RegistryObject:Classification" id="urn:uuid:{uuid.uuid4()}">
              <rim:Slot name="codingScheme"><rim:ValueList><rim:Value>{facility_type_code_scheme}</rim:Value></rim:ValueList></rim:Slot>
              <rim:Name><rim:LocalizedString value="{facility_type_code_display}"/></rim:Name>
            </rim:Classification>
            <rim:Classification classificationScheme="{practice_setting_code_uuid}" classifiedObject="urn:uuid:{document_uuid}" nodeRepresentation="{practice_setting_code}" objectType="urn:oasis:names:tc:ebxml-regrep:ObjectType:RegistryObject:Classification" id="urn:uuid:{uuid.uuid4()}">
              <rim:Slot name="codingScheme"><rim:ValueList><rim:Value>{practice_setting_code_scheme}</rim:Value></rim:ValueList></rim:Slot>
              <rim:Name><rim:LocalizedString value="{practice_setting_code_display}"/></rim:Name>
            </rim:Classification>
            <rim:Classification classificationScheme="{format_code_uuid}" classifiedObject="urn:uuid:{document_uuid}" nodeRepresentation="{format_code}" objectType="urn:oasis:names:tc:ebxml-regrep:ObjectType:RegistryObject:Classification" id="urn:uuid:{uuid.uuid4()}">
              <rim:Slot name="codingScheme"><rim:ValueList><rim:Value>{format_code_scheme}</rim:Value></rim:ValueList></rim:Slot>
              <rim:Name><rim:LocalizedString value="{format_code_display}"/></rim:Name>
            </rim:Classification>
            <rim:ExternalIdentifier identificationScheme="urn:uuid:2e82c1f6-a085-4c72-9da3-8640a32e42ab" value="{document_unique_id}" objectType="urn:oasis:names:tc:ebxml-regrep:ObjectType:RegistryObject:ExternalIdentifier" id="urn:uuid:{uuid.uuid4()}" registryObject="urn:uuid:{document_uuid}">
              <rim:Name><rim:LocalizedString value="XDSDocumentEntry.uniqueId"/></rim:Name>
            </rim:ExternalIdentifier>
            <rim:ExternalIdentifier identificationScheme="urn:uuid:58a6f841-87b3-4a3e-92fd-a8ffeff98427" value="{patient_id}" objectType="urn:oasis:names:tc:ebxml-regrep:ObjectType:RegistryObject:ExternalIdentifier" id="urn:uuid:{uuid.uuid4()}" registryObject="urn:uuid:{document_uuid}">
              <rim:Name><rim:LocalizedString value="XDSDocumentEntry.patientId"/></rim:Name>
            </rim:ExternalIdentifier>
          </rim:ExtrinsicObject>
          <rim:RegistryPackage id="urn:uuid:{submission_set_uuid}" objectType="urn:oasis:names:tc:ebxml-regrep:ObjectType:RegistryObject:RegistryPackage">
            <rim:Slot name="submissionTime"><rim:ValueList><rim:Value>{timestamp}</rim:Value></rim:ValueList></rim:Slot>
            <rim:Name><rim:LocalizedString value="Sample Submission"/></rim:Name>
            <rim:Description><rim:LocalizedString value="Submission of clinical documents"/></rim:Description>
            <rim:Classification classificationScheme="{content_type_code_uuid}" classifiedObject="urn:uuid:{submission_set_uuid}" nodeRepresentation="{content_type_code}" objectType="urn:oasis:names:tc:ebxml-regrep:ObjectType:RegistryObject:Classification" id="urn:uuid:{uuid.uuid4()}">
              <rim:Slot name="codingScheme"><rim:ValueList><rim:Value>{content_type_code_scheme}</rim:Value></rim:ValueList></rim:Slot>
              <rim:Name><rim:LocalizedString value="{content_type_code_display}"/></rim:Name>
            </rim:Classification>
            <rim:ExternalIdentifier identificationScheme="urn:uuid:96fdda7c-d067-4183-912e-bf5ee74998a8" value="{submission_set_unique_id}" objectType="urn:oasis:names:tc:ebxml-regrep:ObjectType:RegistryObject:ExternalIdentifier" id="urn:uuid:{uuid.uuid4()}" registryObject="urn:uuid:{submission_set_uuid}">
              <rim:Name><rim:LocalizedString value="XDSSubmissionSet.uniqueId"/></rim:Name>
            </rim:ExternalIdentifier>
            <rim:ExternalIdentifier identificationScheme="urn:uuid:554ac39e-e3fe-47fe-b233-965d2a147832" value="1.3.6.1.4.1.21367.2009.1.2.1" objectType="urn:oasis:names:tc:ebxml-regrep:ObjectType:RegistryObject:ExternalIdentifier" id="urn:uuid:{uuid.uuid4()}" registryObject="urn:uuid:{submission_set_uuid}">
              <rim:Name><rim:LocalizedString value="XDSSubmissionSet.sourceId"/></rim:Name>
            </rim:ExternalIdentifier>
            <rim:ExternalIdentifier identificationScheme="urn:uuid:6b5aea1a-874d-4603-a4bc-96a0a7b38446" value="{patient_id}" objectType="urn:oasis:names:tc:ebxml-regrep:ObjectType:RegistryObject:ExternalIdentifier" id="urn:uuid:{uuid.uuid4()}" registryObject="urn:uuid:{submission_set_uuid}">
              <rim:Name><rim:LocalizedString value="XDSSubmissionSet.patientId"/></rim:Name>
            </rim:ExternalIdentifier>
          </rim:RegistryPackage>
          <rim:Association associationType="urn:oasis:names:tc:ebxml-regrep:AssociationType:HasMember" sourceObject="urn:uuid:{submission_set_uuid}" targetObject="urn:uuid:{document_uuid}" id="urn:uuid:{association_uuid}" objectType="urn:oasis:names:tc:ebxml-regrep:ObjectType:RegistryObject:Association">
            <rim:Slot name="SubmissionSetStatus"><rim:ValueList><rim:Value>Original</rim:Value></rim:ValueList></rim:Slot>
          </rim:Association>
        </rim:RegistryObjectList>
      </lcm:SubmitObjectsRequest>
      <xdsb:Document id="urn:uuid:{document_uuid}">{document_content_b64}</xdsb:Document>
    </xdsb:ProvideAndRegisterDocumentSetRequest>
  </soapenv:Body>
</soapenv:Envelope>'''

        # Build the multipart message
        multipart_body = (
            f"--{boundary}\r\n"
            f'Content-Type: application/xop+xml; charset=UTF-8; type="application/soap+xml"\r\n'
            f'Content-Transfer-Encoding: binary\r\n'
            f'Content-ID: <root.message@xds>\r\n\r\n'
            f'{soap_xml}\r\n'
            f"--{boundary}\r\n"
            f"Content-Type: {mime_type}\r\n"
            f"Content-Transfer-Encoding: binary\r\n"
            f"Content-ID: <{document_uuid}>\r\n\r\n"
        ).encode('utf-8') + document_content + f"\r\n--{boundary}--\r\n".encode('utf-8')

        # Set headers
        headers = {
            "Content-Type": f'multipart/related; boundary="{boundary}"; type="application/xop+xml"; '
                          f'start="<root.message@xds>"; start-info="application/soap+xml"; '
                          f'action="urn:ihe:iti:2007:ProvideAndRegisterDocumentSet-b"',
            "MIME-Version": "1.0"
        }

        # Send request to XDS.b repository
        xds_url = "http://localhost:8084/xdstools7.12.0/sim/default__rep_01/rep/prb"
        response = requests.post(xds_url, data=multipart_body, headers=headers)

        # Print request and response for debugging
        print("===== BEGIN GENERATED SOAP ENVELOPE SENT TO XDS =====")
        print(soap_xml)
        print("===== END GENERATED SOAP ENVELOPE =====")
        print("===== XDS RESPONSE STATUS: ", response.status_code)
        print("===== XDS RESPONSE BODY: ", response.text)

        return jsonify({
            "status": response.status_code,
            "xds_response": response.text
        }), response.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def build_xds_message(pdf_bytes, filename):
    """Build a complete XDS.b message with proper MIME packaging"""
    # Generate unique IDs
    doc_id = f"Document_{uuid.uuid4()}"
    message_id = f"urn:uuid:{uuid.uuid4()}"
    
    # Build the SOAP envelope
    soap_xml = f"""<?xml version='1.0' encoding='UTF-8'?>
<soapenv:Envelope xmlns:soapenv="http://www.w3.org/2003/05/soap-envelope"
                  xmlns:wsa="http://www.w3.org/2005/08/addressing"
                  xmlns:xdsb="urn:ihe:iti:xds-b:2007"
                  xmlns:lcm="urn:oasis:names:tc:ebxml-regrep:xsd:lcm:3.0"
                  xmlns:rim="urn:oasis:names:tc:ebxml-regrep:xsd:rim:3.0">
  <soapenv:Header>
    <wsa:To>http://localhost:8084/xdstools7.12.0/sim/default__rep_01/rep/prb</wsa:To>
    <wsa:MessageID>{message_id}</wsa:MessageID>
    <wsa:Action soapenv:mustUnderstand="1">urn:ihe:iti:2007:ProvideAndRegisterDocumentSet-b</wsa:Action>
  </soapenv:Header>
  <soapenv:Body>
    <xdsb:ProvideAndRegisterDocumentSetRequest>
      <lcm:SubmitObjectsRequest>
        <rim:RegistryObjectList>
          <rim:ExtrinsicObject id="urn:uuid:{doc_id}" mimeType="application/pdf" 
              objectType="urn:uuid:7edca82f-054d-47f2-a032-9b2a5b5186c1">
            <rim:Slot name="creationTime">
              <rim:ValueList>
                <rim:Value>{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}</rim:Value>
              </rim:ValueList>
            </rim:Slot>
            <rim:Name>
              <rim:LocalizedString value="{filename}"/>
            </rim:Name>
            <rim:Classification classificationScheme="urn:uuid:93606bcf-9494-43ec-9b4e-a7748d1a838d"
                classifiedObject="urn:uuid:{doc_id}" nodeRepresentation="" 
                objectType="urn:oasis:names:tc:ebxml-regrep:ObjectType:RegistryObject:Classification"/>
          </rim:ExtrinsicObject>
        </rim:RegistryObjectList>
      </lcm:SubmitObjectsRequest>
      <xdsb:Document id="urn:uuid:{doc_id}">{base64.b64encode(pdf_bytes).decode('utf-8')}</xdsb:Document>
    </xdsb:ProvideAndRegisterDocumentSetRequest>
  </soapenv:Body>
</soapenv:Envelope>"""

    # Create MIME message
    boundary = f"MIMEBoundary_{uuid.uuid4().hex}"
    msg = MIMEMultipart('related', boundary=boundary, type='application/xop+xml')
    
    # SOAP part
    soap_part = MIMEText(soap_xml, 'xml', 'utf-8')
    soap_part.add_header('Content-Type', 'application/xop+xml; charset=UTF-8; type="application/soap+xml"')
    soap_part.add_header('Content-ID', '<root.message@cxf.apache.org>')
    soap_part.add_header('Content-Transfer-Encoding', '8bit')
    msg.attach(soap_part)

    # PDF part
    pdf_part = MIMEApplication(
        pdf_bytes,
        'pdf',
        _encoder=lambda x: x  # Disable base64 encoding
    )
    pdf_part.add_header('Content-Type', 'application/pdf')
    pdf_part.add_header('Content-ID', f'<{doc_id}>')
    pdf_part.add_header('Content-Transfer-Encoding', 'binary')
    msg.attach(pdf_part)

    # Generate the MIME message
    msg_bytes = BytesIO()
    gen = BytesGenerator(msg_bytes, mangle_from_=False)
    gen.flatten(msg)
    
    content_type = (
        f'multipart/related; '
        f'boundary="{boundary}"; '
        f'type="application/xop+xml"; '
        f'start="<root.message@cxf.apache.org>"; '
        f'start-info="application/soap+xml"'
    )

    return msg_bytes.getvalue(), content_type

def handle_response(response):
    """Process the XDS repository response"""
    if response.status_code != 200:
        return jsonify({
            'error': 'XDS repository error',
            'status_code': response.status_code,
            'response': response.text
        }), 500
    
    try:
        # Parse the response to extract useful information
        return jsonify({
            'status_code': response.status_code,
            'response': response.text,
            # 'message': 'Document submitted successfully'
        })
    except Exception as e:
        return jsonify({
            'error': 'Failed to parse response',
            'status_code': response.status_code,
            'response': response.text,
            'exception': str(e)
        }), 500



if __name__ == "__main__":
    app.run(debug=True, port=5002)