"""
URL routing for hrm API v1.
"""

from django.urls import path

from apps.hrm.api.v1 import views

app_name = "hrm_v1"

urlpatterns = [
    # Employees
    path("employees/", views.employee_list_view, name="employee_list"),
    path("employees/create/", views.employee_create_view, name="employee_create"),
    path("employees/<uuid:pk>/", views.employee_detail_view, name="employee_detail"),
    path("employees/<uuid:pk>/update/", views.employee_update_view, name="employee_update"),
    path(
        "employees/<uuid:pk>/update-salary-title/",
        views.employee_update_salary_title_view,
        name="employee_update_salary_title",
    ),
    # Contracts
    path("contracts/", views.contract_create_or_renew_view, name="contract_create_or_renew"),
    path("contracts/<uuid:pk>/terminate/", views.contract_terminate_view, name="contract_terminate"),
    # Attendances
    path("attendances/", views.attendance_list_view, name="attendance_list"),
    path("attendances/batch/", views.attendance_batch_view, name="attendance_batch"),
    # Leave Requests
    path("leave-requests/", views.leave_request_list_view, name="leave_request_list"),
    path("leave-requests/create/", views.leave_request_create_view, name="leave_request_create"),
    path("leave-requests/<uuid:pk>/approve/", views.leave_request_approve_view, name="leave_request_approve"),
    # Salary Slips
    path("salary-slips/", views.salary_slip_list_view, name="salary_slip_list"),
    path("salary-periods/", views.salary_periods_list_view, name="salary_periods_list"),
    path("salary-slips/initialize/", views.salary_slip_initialize_view, name="salary_slip_initialize"),
    path("salary-slips/bulk-confirm-pay/", views.salary_slip_bulk_confirm_view, name="salary_slip_bulk_confirm"),
    path("salary-slips/<uuid:pk>/calculate/", views.salary_slip_calculate_view, name="salary_slip_calculate"),
    path("salary-slips/<uuid:pk>/approve/", views.salary_slip_approve_view, name="salary_slip_approve"),
    # Rewards & Disciplines
    path("rewards/", views.reward_list_create_view, name="reward_list_create"),
    path("rewards/<uuid:pk>/approve/", views.reward_approve_view, name="reward_approve"),
    path("disciplines/", views.discipline_list_create_view, name="discipline_list_create"),
    path("disciplines/<uuid:pk>/approve/", views.discipline_approve_view, name="discipline_approve"),
    path("employment-histories/", views.employment_history_list_view, name="employment_history_list"),
    path(
        "employment-histories/<uuid:pk>/approve/",
        views.employment_history_approve_view,
        name="employment_history_approve",
    ),
    # Public Holidays
    path("public-holidays/", views.public_holiday_list_create_view, name="public_holiday_list_create"),
    path(
        "public-holidays/<uuid:pk>/",
        views.public_holiday_detail_update_delete_view,
        name="public_holiday_detail_update_delete",
    ),
]
