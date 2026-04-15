"""ATC operator routes and related JSON APIs."""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import login_required, current_user

from app.models import FlightPlan, TrackData
from app.services import audit_service, atc_service
from app.utils.decorators import atc_required
from modules.flight_plan_form_io import default_form_fields, parse_raw_to_form_fields
from modules.flight_plan_parser import FlightPlanParser
from modules.validators import validate_atc_estimates

bp = Blueprint('atc', __name__)


@bp.route('/atc/dashboard')
@login_required
@atc_required
def atc_dashboard():
    """ATC dashboard"""
    recent_tracks = TrackData.query.filter_by(created_by=current_user.id).order_by(
        TrackData.created_at.desc()
    ).limit(10).all()

    return render_template('atc/dashboard.html', recent_tracks=recent_tracks)


@bp.route('/atc/flight-plan', methods=['GET', 'POST'])
@login_required
@atc_required
def atc_flight_plan():
    """ATC flight plan retrieval and processing"""
    parsed_data = None
    callsign = ''
    error = None

    if request.method == 'POST':
        callsign = request.form.get('callsign', '').strip().upper()
        result = atc_service.lookup_and_parse_flight_plan(callsign)
        error = result['error']
        parsed_data = result['parsed_data']

        if result['flight_plan_id'] and parsed_data:
            session['current_flight_plan_id'] = result['flight_plan_id']
            session['current_parsed_data'] = parsed_data
            audit_service.log_action('FLIGHT_PLAN_RETRIEVED', f'Callsign: {callsign}')
        elif error and 'not found' in error.lower():
            audit_service.log_action('FLIGHT_PLAN_NOT_FOUND', f'Callsign: {callsign}')

    return render_template(
        'atc/flight_plan.html',
        callsign=callsign,
        parsed_data=parsed_data,
        error=error
    )


@bp.route('/atc/estimates', methods=['GET', 'POST'])
@login_required
@atc_required
def atc_estimates():
    """ATC estimate entry and validation"""
    if 'current_parsed_data' not in session:
        flash('Please retrieve a flight plan first', 'warning')
        return redirect(url_for('atc.atc_flight_plan'))

    parsed_data = session['current_parsed_data']
    flight_plan_id = session.get('current_flight_plan_id')

    existing_active_track = atc_service.get_existing_active_track(flight_plan_id)

    if existing_active_track:
        flash('Estimate cannot be entered. This flight plan already has an active track.', 'error')
        audit_service.log_action(
            'DUPLICATE_ACTIVATION_BLOCKED',
            f'Flight Plan ID: {flight_plan_id}, Callsign: {parsed_data["callsign"]}'
        )
        return render_template(
            'atc/estimates.html',
            parsed_data=parsed_data,
            validation_result=None,
            submitted=False,
            already_active=True
        )

    validation_result = None
    submitted = False

    if request.method == 'POST':
        eto = request.form.get('eto', '').strip()
        cfl = request.form.get('cfl', '').strip()
        ssr = request.form.get('ssr', '').strip()

        outcome = atc_service.process_estimates_submission(
            parsed_data, flight_plan_id, current_user.id, eto, cfl, ssr
        )
        validation_result = outcome['validation_result']

        if outcome.get('flash_error'):
            flash(outcome['flash_error'], 'error')
        if outcome.get('log_ssr_block'):
            act, det = outcome['log_ssr_block']
            audit_service.log_action(act, det)
        if outcome.get('log_track_created'):
            act, det = outcome['log_track_created']
            audit_service.log_action(act, det)
            session['current_track_id'] = outcome['new_track_id']
            submitted = outcome['submitted']
            flash('Estimates submitted successfully! Ready to transfer to Defense.', 'success')

    return render_template(
        'atc/estimates.html',
        parsed_data=parsed_data,
        validation_result=validation_result,
        submitted=submitted,
        already_active=False
    )


@bp.route('/atc/transfer', methods=['POST'])
@login_required
@atc_required
def atc_transfer():
    """Transfer track data to Defense"""
    track_id = session.get('current_track_id')

    if not track_id:
        flash('No track data to transfer', 'error')
        return redirect(url_for('atc.atc_dashboard'))

    track, defense_msg = atc_service.transfer_track_to_defense(track_id)

    if not track:
        flash('Track data not found', 'error')
        return redirect(url_for('atc.atc_dashboard'))

    audit_service.log_action(
        'DATA_TRANSFERRED',
        f'Track ID: {track.id}, Defense Message ID: {defense_msg.id}'
    )

    session.pop('current_flight_plan_id', None)
    session.pop('current_parsed_data', None)
    session.pop('current_track_id', None)

    flash('Data successfully transferred to Defense!', 'success')
    return redirect(url_for('atc.atc_dashboard'))


@bp.route('/atc/add-flight-plan', methods=['GET', 'POST'])
@login_required
@atc_required
def atc_add_flight_plan():
    """Add new flight plan to database"""
    if request.method == 'POST':
        callsign = request.form.get('callsign', '').strip().upper()
        raw_flight_plan = request.form.get('raw_flight_plan', '').strip()
        replace_existing = request.form.get('replace_existing') == 'true'

        outcome = atc_service.add_flight_plan_post(callsign, raw_flight_plan, replace_existing)

        if outcome.get('flash'):
            msg, cat = outcome['flash']
            flash(msg, cat)

        if outcome['action'] == 'render':
            ctx = outcome.get('context') or {}
            return render_template(outcome['template'], **ctx)

        if outcome['action'] == 'redirect':
            for log_pair in outcome.get('logs', []):
                audit_service.log_action(log_pair[0], log_pair[1])
            return redirect(url_for('atc.atc_manage_flight_plans'))

    return render_template(
        'atc/add_flight_plan.html',
        initial_form=default_form_fields(),
        callsign='',
    )


@bp.route('/atc/api/flight-plan/form-parse', methods=['POST'])
@login_required
@atc_required
def atc_api_flight_plan_form_parse():
    """Parse raw ICAO text into structured form fields (JSON)."""
    data = request.get_json(silent=True) or {}
    raw = (data.get('raw_flight_plan') or '').strip()
    if not raw:
        return jsonify(
            {
                'ok': False,
                'fields': default_form_fields(),
                'notes': ['Empty flight plan'],
                'parser_ok': False,
                'parser_errors': ['Empty flight plan'],
            }
        ), 400

    fields, notes = parse_raw_to_form_fields(raw)
    parser = FlightPlanParser()
    parsed = parser.parse(raw)
    parser_ok = parsed is not None
    return jsonify(
        {
            'ok': parser_ok,
            'fields': fields,
            'notes': notes,
            'parser_ok': parser_ok,
            'parser_errors': parser.get_errors() if not parser_ok else [],
        }
    ), (200 if parser_ok else 400)


@bp.route('/atc/edit-flight-plan/<int:plan_id>', methods=['GET', 'POST'])
@login_required
@atc_required
def atc_edit_flight_plan(plan_id):
    """Edit existing flight plan text in the database (same callsign as filed in ICAO text)."""
    flight_plan = FlightPlan.query.get_or_404(plan_id)

    if request.method == 'POST':
        raw = request.form.get('raw_flight_plan', '').strip()
        outcome = atc_service.edit_flight_plan_post(flight_plan, raw)

        if outcome.get('flash'):
            msg, cat = outcome['flash']
            flash(msg, cat)

        if outcome['action'] == 'render':
            ctx = outcome.get('context') or {}
            return render_template(outcome['template'], **ctx)

        if outcome['action'] == 'redirect':
            for log_pair in outcome.get('logs', []):
                audit_service.log_action(log_pair[0], log_pair[1])
            return redirect(url_for('atc.atc_manage_flight_plans'))

    initial_form, _ = parse_raw_to_form_fields(flight_plan.raw_flight_plan or '')
    return render_template(
        'atc/edit_flight_plan.html',
        flight_plan=flight_plan,
        raw_value=flight_plan.raw_flight_plan or '',
        initial_form=initial_form,
    )


@bp.route('/atc/manage-flight-plans')
@login_required
@atc_required
def atc_manage_flight_plans():
    """Manage flight plans - view and delete"""
    ctx = atc_service.get_manage_flight_plans_context()
    return render_template('atc/manage_flight_plans.html', **ctx)


@bp.route('/atc/delete-flight-plan/<int:plan_id>', methods=['POST'])
@login_required
@atc_required
def atc_delete_flight_plan(plan_id):
    """Delete a flight plan"""
    flight_plan = FlightPlan.query.get_or_404(plan_id)
    terminate_tracks = request.form.get('terminate_tracks') == 'true'

    result = atc_service.delete_atc_flight_plan(flight_plan, terminate_tracks)

    if result.get('redirect_warning'):
        flash(result['flash'][0], result['flash'][1])
        return redirect(url_for('atc.atc_manage_flight_plans'))

    flash(result['flash'][0], result['flash'][1])
    for act, det in result.get('logs', []):
        audit_service.log_action(act, det)

    return redirect(url_for('atc.atc_manage_flight_plans'))


@bp.route('/api/validate-estimates', methods=['POST'])
@login_required
@atc_required
def api_validate_estimates():
    """AJAX endpoint for real-time estimate validation"""
    data = request.get_json()

    eto = data.get('eto', '')
    cfl = data.get('cfl', '')
    ssr = data.get('ssr', '')

    result = validate_atc_estimates(eto, cfl, ssr)

    return jsonify(result)


@bp.route('/api/flight-plan/<callsign>')
@login_required
@atc_required
def api_flight_plan(callsign):
    """API endpoint to get flight plan by callsign"""
    ok, payload, code = atc_service.get_api_flight_plan(callsign)
    if ok:
        return jsonify(payload)
    return jsonify(payload), code


@bp.route('/atc/deactivate-track/<int:track_id>', methods=['POST'])
@login_required
@atc_required
def atc_deactivate_track(track_id):
    """
    Deactivate an active track (JSON). Removes it from defense radar active queries.
    CSRF: send header ``X-CSRFToken`` (or form field ``csrf_token``) for AJAX.
    """
    try:
        track = atc_service.deactivate_track(track_id, current_user)
    except atc_service.TrackNotFoundError:
        return jsonify({'ok': False, 'message': f'Track not found (id {track_id}).'}), 404
    except atc_service.TrackAlreadyInactiveError:
        return jsonify({'ok': False, 'message': 'Track is already inactive'}), 200
    except atc_service.TrackDeactivateError as e:
        return jsonify({'ok': False, 'message': str(e)}), 400

    audit_service.log_action(
        'Track Deactivated',
        f'Track ID: {track.id}, Callsign: {track.callsign}, User: {current_user.username}'
    )
    return jsonify({
        'ok': True,
        'message': 'Track deactivated successfully.',
        'callsign': track.callsign,
        'track_id': track.id,
    })
