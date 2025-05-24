guard_mappings = {
    "salesforce": {
        "salesforce_create_contact_creation": "modifyContacts",
        "salesforce_create_account_creation": "modifyAccounts",
        "salesforce_create_opportunity_creation": "modifyOpportunities",
        "salesforce_update_contact_creation": "modifyContacts",
        "salesforce_get_account_details_retrieval": "readEnabled",
        "salesforce_query_retrieval": "readEnabled",
        "salesforce_retrieval_get_accounts": "readEnabled",
        "salesforce_get_contacts_retrieval": "readEnabled",
        "salesforce_get_account_id_retrieval": "readEnabled",
        "salesforce_get_schemas_retrieval": "readEnabled",
    },
    "sharepoint": {
        "sharepoint_send_email_admin": "canSend",
        "sharepoint_get_users_info_admin": "readEnabled",
        "sharepoint_schedule_meeting_admin": "writeEnabled",
        "sharepoint_get_documents_retrieval": "readEnabled",
        "sharepoint_query_documents_retrieval": "readEnabled",
    },
    "zendesk": {
        "zendesk_create_ticket_creation": "createTickets",
        "zendesk_add_comment_admin": "addComments",
        "zendesk_get_ticket_retrieval": "readEnabled",
        "zendesk_upload_attachment_admin": "canUpload",
        "zendesk_get_help_center_categories_retrieval": "readEnabled",
        "zendesk_get_category_sections_retrieval": "readEnabled",
        "zendesk_get_section_articles_retrieval": "readEnabled",
    }
}