from django.contrib.auth.decorators import login_required
from NearBeach.models import *
from django.core import serializers
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseRedirect, JsonResponse
from django.urls import reverse
from django.template import loader
from django.db.models import Sum, Q, Min
from NearBeach.forms import *
from NearBeach.user_permissions import return_user_permission_level


import json

def get_requirement_item_status_list(request,requirement_id):
    # Get all status - even deleted ones.
    status_list = list_of_requirement_item_status.objects.all()

    # Send back json data
    json_results = serializers.serialize('json', status_list)

    return HttpResponse(json_results, content_type='application/json')


def get_requirement_item_type_list(request,requirement_id):
    # Get all status - even deleted ones.
    type_list = list_of_requirement_item_type.objects.all()

    # Send back json data
    json_results = serializers.serialize('json', type_list)

    return HttpResponse(json_results, content_type='application/json')

def get_requirement_items(request,requirement_id):
    # Get all the requirement items assigned to the requirement
    requirement_item_results = requirement_item.objects.filter(
        is_deleted="FALSE",
        requirement_id=requirement_id,
    )

    # Send back json data
    json_results = serializers.serialize('json', requirement_item_results)

    return HttpResponse(json_results, content_type='application/json')



def get_user_requirement_permissions(request,requirement_id):
    """
    Use the requirement_id and find out if the user has access to this requirement
    :param requirement_id:
    :return:
    """
    requirement_groups = object_assignment.objects.filter(
        is_deleted="FALSE",
        #requirement_id=requirement_id
    ).values('group_id')

    if requirement_id > 0:
        # Make sure to filter by requirement groups
        requirement_groups = requirement_groups.filter(
            requirement_id=requirement_id
        )

    return return_user_permission_level(request, requirement_groups, ['requirement','requirement_link'])


@login_required(login_url='login',redirect_field_name="")
def new_requirement(request, location_id="", destination=""):
    """
    Loads the new requirement page
    :param request:
    :param location_id:
    :param destination:
    :return:
    """
    # Get user permission
    permission_results = get_user_requirement_permissions(request,0)

    # If user has no permissions to create requirements, then send them to the appropriate location
    if permission_results['requirement'] <= 2:
        # Users can not create requirement.
        return HttpResponseRedirect(reverse('permission_denied'))

    #Extract Data
    status_list = list_of_requirement_status.objects.filter(
        is_deleted="FALSE",
        requirement_status_is_closed="FALSE",
    )

    type_list = list_of_requirement_type.objects.filter(
        is_deleted="FALSE",
    )

    group_results = group.objects.filter(
        is_deleted="FALSE",
    )

    #Load template
    t = loader.get_template('NearBeach/requirements/new_requirements.html')

    # context
    c = {
        'status_list': serializers.serialize("json",status_list),
        'type_list': serializers.serialize("json",type_list),
        'group_results': serializers.serialize("json",group_results),
    }

    return HttpResponse(t.render(c, request))

@login_required(login_url='login',redirect_field_name='')
def new_requirement_save(request, location_id="", destination=""):
    # Make sure this is a post
    if not request.method == "POST":
        #Give the user a 404
        return HttpResponseBadRequest("Sorry - Post only")

    # Get user permission
    permission_results = get_user_requirement_permissions(request,0)

    # If user has no permissions to create requirements, then send them to the appropriate location
    if permission_results['requirement'] <= 2:
        # Users can not create requirement.
        return HttpResponseRedirect(reverse('permission_denied'))

    # Get the data and place into the form

    form = NewRequirementForm(request.POST)

    if not form.is_valid():
        # Something went wrong with the form.
        return HttpResponseBadRequest("There was something wrong with the form")

    print("ORGANISATION")
    print(form.cleaned_data['organisation'])

    # Save the form
    submit_requirement = requirement(
        requirement_title=form.cleaned_data['requirement_title'],
        requirement_scope=form.cleaned_data['requirement_scope'],
        organisation=form.cleaned_data['organisation'],
        requirement_status=form.cleaned_data['requirement_status'],
        requirement_type=form.cleaned_data['requirement_type'],
        change_user=request.user,
        creation_user=request.user,
    )
    submit_requirement.save()

    # Get the group list and apply the permissions
    group_list = request.POST.getlist("group_list")

    for single_group in group_list:
        # Get the group instance
        group_instance = group.objects.get(group_id=single_group)

        # Save the group instance against object assignment
        submit_object_assignment = object_assignment(
            group_id=group_instance,
            requirement_id=submit_requirement,
            change_user=request.user,
        )

        # Save
        submit_object_assignment.save()

    # Send back requirement_information URL
    return HttpResponse(reverse('requirement_information',args={submit_requirement.requirement_id}))



@login_required(login_url='login',redirect_field_name='')
def requirement_information(request, requirement_id):
    """
    Loads the requirement information.
    :param request:
    :param requirement_id:
    :return:
    """
    # Get the requirement information
    requirement_results = requirement.objects.get(requirement_id=requirement_id)

    # Check the permissions
    permission_results = get_user_requirement_permissions(request,requirement_id)

    # If user has no permissions to this requirement send them to the appropriate location
    if permission_results['requirement'] == 0:
        # Users who create the requirement get at least read only
        if requirement_results.creation_user == request.user:
            return HttpResponseRedirect(reverse('requirement_readonly', args={requirement_id}))

        # Users who did not create the requirement get sent to permission denied.
        return HttpResponseRedirect(reverse('permission_denied'))


    # If the requirement has been closed - send user to the read only section
    if requirement_results.requirement_status.requirement_status == "Completed":
        return HttpResponseRedirect(reverse('requirement_readonly', args={requirement_id}))


    #Load template
    t = loader.get_template('NearBeach/requirements/requirement_information.html')

    #Get any extra data required
    organisation_results = organisation.objects.get(
        organisation_id=requirement_results.organisation_id,
    )

    status_list = list_of_requirement_status.objects.filter(
        is_deleted="FALSE",
        requirement_status_is_closed="FALSE",
    )

    type_list = list_of_requirement_type.objects.filter(
        is_deleted="FALSE",
    )

    group_results = group.objects.filter(
        is_deleted="FALSE",
    )

    requirement_item_results = requirement_item.objects.filter(
        is_deleted="FALSE",
        requirement_id=requirement_id,
    )

    # context
    c = {
        'group_results': serializers.serialize("json", group_results),
        'organisation_results': serializers.serialize("json", [organisation_results]),
        'permission_results': permission_results,
        'requirement_results': serializers.serialize("json", [requirement_results]),
        'requirement_id': requirement_id,
        'requirement_item_results': serializers.serialize("json",requirement_item_results),
        'status_list': serializers.serialize("json", status_list),
        'type_list': serializers.serialize("json", type_list),

    }

    return HttpResponse(t.render(c, request))


def update_requirement(request,requirement_id):
    return False