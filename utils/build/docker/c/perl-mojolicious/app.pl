#!/usr/bin/env perl

use v5.20;
use strict;
use warnings;

use Mojo::JSON qw(decode_json encode_json);
use Mojo::UserAgent;
use Mojolicious::Lite -signatures;

my $port = 7777;
my $observed_headers_response_header = 'X-System-Tests-Observed-Request-Headers';
my $listen_host = ($ENV{DD_AGENT_HOST} // '') =~ /:/ ? '[::]' : '0.0.0.0';

app->config(
    hypnotoad => {
        listen  => ["http://${listen_host}:${port}"],
        workers => 2,
    },
);

sub observed_headers ($c) {
    my $headers = $c->req->headers->to_hash;
    return {map { lc $_ => $headers->{$_} } keys %$headers};
}

sub response_headers ($headers) {
    my $hash = $headers->to_hash;
    return {map { lc $_ => $hash->{$_} } keys %$hash};
}

sub request ($method, $url, $headers = {}, $body = undef) {
    my $ua = Mojo::UserAgent->new(max_redirects => 10);
    my $tx = $ua->build_tx($method => $url => $headers => $body);
    return $ua->start($tx)->result;
}

hook after_dispatch => sub ($c) {
    $c->res->headers->header($observed_headers_response_header => encode_json(observed_headers($c)));
};

any '/' => sub ($c) { $c->render(text => "Hello world!\n") };

any '/*route' => sub ($c) {
    my $path = '/' . ($c->stash('route') // '');

    if ($path eq '/healthcheck') {
        open my $version_file, '<', '/opt/datadog/apm/library/c/version' or die "Cannot read version: $!";
        my $version = <$version_file>;
        close $version_file;
        chomp $version;
        return $c->render(json => {status => 'ok', library => {name => 'c', version => $version}});
    }

    if ($path eq '/headers') {
        $c->res->headers->content_language('en-US');
        $c->res->headers->content_type('text');
        return $c->render(data => "Hello headers!\n");
    }

    if ($path =~ m{^/(?:params|sample_rate_route)/}) {
        return $c->render(text => "Hello world!\n");
    }

    if ($path eq '/status') {
        return $c->render(status => ($c->param('code') // 200), data => '');
    }

    if ($path eq '/returnheaders' || $path eq '/returnheaders/') {
        return $c->render(json => observed_headers($c));
    }

    if ($path eq '/read_file') {
        my $requested_file = $c->param('file') // '';
        return $c->render(status => 400, json => {error => 'file is not allowed'}) if $requested_file ne '/proc/self/cgroup';
        open my $file, '<', $requested_file or die "Cannot read ${requested_file}: $!";
        local $/;
        my $content = <$file>;
        close $file;
        return $c->render(data => $content);
    }

    if ($path eq '/requestdownstream') {
        my $result = request('GET', 'http://127.0.0.1:7777/returnheaders');
        return $c->render(data => $result->body, format => 'json');
    }

    if ($path eq '/make_distant_call') {
        my $url = $c->param('url');
        return $c->render(status => 400, json => {error => 'url query parameter is required'}) unless defined $url;
        my $result = request('GET', $url);
        my $raw_headers = $result->headers->header($observed_headers_response_header) // '{}';
        my $request_headers = eval { decode_json($raw_headers) } // {};
        return $c->render(
            json => {
                url              => $url,
                status_code      => $result->code,
                request_headers  => $request_headers,
                response_headers => response_headers($result->headers),
            }
        );
    }

    if ($path eq '/external_request') {
        my $query = $c->req->url->query->to_hash;
        my $status = delete($query->{status}) // 200;
        my $url_extra = delete($query->{url_extra}) // '';
        my %headers = %$query;
        $headers{'content-type'} = $c->req->headers->content_type if defined $c->req->headers->content_type;
        my $result = request($c->req->method, "http://internal_server:8089/mirror/${status}${url_extra}", \%headers, $c->req->body);
        my $payload = eval { decode_json($result->body) };
        return $c->render(json => {status => $result->code, payload => $payload, headers => response_headers($result->headers)});
    }

    if ($path eq '/external_request/redirect') {
        my $redirect_count = $c->param('totalRedirects') // 0;
        my $result = request('GET', "http://internal_server:8089/redirect?totalRedirects=${redirect_count}");
        return $c->render(json => {status => $result->is_success ? 200 : undef});
    }

    if ($path eq '/spans' || $path eq '/waf') {
        return $c->render(text => "Hello world!\n");
    }

    return $c->render(status => 404, text => "Not found\n");
};

app->start;
